from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from tint_sis.adapters.homologos_filter import run_homologos_filter
from tint_sis.db import repository
from tint_sis.db.database import DEFAULT_DB_PATH, get_session
from tint_sis.routing import find_homologos_expert_pairs, find_homologos_master_pair

ProgressCallback = Callable[[dict], None]


def _emit(cb: ProgressCallback | None, **event: object) -> None:
    if cb is not None:
        cb(event)


@dataclass
class GeneratedFile:
    """Un archivo de salida concreto (alimenta la vista Resultados sin re-parsear)."""

    grupo: str
    tipo: str  # ".csv" | ".xlsx"
    filas: int
    ruta: str
    software: str = "xData"


@dataclass
class PipelineSummary:
    ingestion_warnings: list[str] = field(default_factory=list)
    archivos_csv: list[Path] = field(default_factory=list)
    archivos_excel_passthrough: list[Path] = field(default_factory=list)
    archivos: list[GeneratedFile] = field(default_factory=list)


def run_pipeline(
    input_dir: Path,
    output_dir: Path,
    db_path: Path = DEFAULT_DB_PATH,
    *,
    enabled_grupos: set[str] | None = None,
    homologos_master_name: str | None = None,
    expert_glob: str | None = None,
    on_progress: ProgressCallback | None = None,
) -> PipelineSummary:
    """Cruza el archivo experto maestro (xData_DATACOMPLETA_<fecha>.xlsx) contra
    homologos_TINT.xlsx y genera, por cada tienda habilitada, <grupo>_ready.xlsx +
    <grupo>_ready.csv en output_dir. Unico flujo del sistema (el piloto
    CorobLab/FORMULARIO se retiro; ver GUIA_USO.md).

    `on_progress`, si se pasa, recibe eventos {fase, item, indice, total, mensaje}
    (fases: 'inicio', 'tienda_inicio', 'tienda_ok', 'fin'). `enabled_grupos` /
    `homologos_master_name` / `expert_glob` permiten pisar los defaults del codigo
    desde config."""
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)

    # Los archivos finales se ordenan por software dentro de la carpeta de salida:
    # <output_dir>/xData/... (por defecto data/output/xData/). Hoy el unico flujo
    # es xData; cuando entre SANTINT sus salidas van a <output_dir>/SANTINT/.
    xdata_out = output_dir / "xData"

    summary = PipelineSummary()

    master_kwargs = {}
    if homologos_master_name is not None:
        master_kwargs["master_name"] = homologos_master_name
    if expert_glob is not None:
        master_kwargs["expert_glob"] = expert_glob

    session = get_session(db_path)
    try:
        batch = repository.create_batch(session, origen_dir=str(input_dir))

        homologos_pairs = []
        master_pair = find_homologos_master_pair(input_dir, **master_kwargs)
        if master_pair is not None:
            homologos_pairs.append(master_pair)
        homologos_pairs.extend(find_homologos_expert_pairs(input_dir))

        _emit(on_progress, fase="inicio", total=len(homologos_pairs), mensaje="Iniciando ciclo")

        for pair in homologos_pairs:
            results, warns = run_homologos_filter(
                pair.expert_path,
                pair.homologos_path,
                xdata_out,
                enabled_grupos=enabled_grupos,
                on_progress=on_progress,
            )
            summary.ingestion_warnings.extend(warns)
            for result in results:
                summary.archivos_excel_passthrough.append(result.xlsx_path)
                repository.record_generated_file(
                    session, batch, result.grupo, "homologos_filter_xlsx", str(result.xlsx_path)
                )
                summary.archivos_csv.append(result.csv_path)
                repository.record_generated_file(
                    session, batch, result.grupo, "homologos_filter_csv", str(result.csv_path)
                )
                summary.archivos.append(
                    GeneratedFile(result.grupo, ".xlsx", result.filas_filtradas, str(result.xlsx_path))
                )
                summary.archivos.append(
                    GeneratedFile(result.grupo, ".csv", result.filas_filtradas, str(result.csv_path))
                )

        session.commit()
    finally:
        session.close()

    _emit(on_progress, fase="fin", mensaje="Ciclo terminado", generados=len(summary.archivos))
    return summary
