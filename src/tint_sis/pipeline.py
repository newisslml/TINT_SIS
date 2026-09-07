from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from tint_sis.adapters.homologos_filter import run_homologos_filter
from tint_sis.db import repository
from tint_sis.db.database import DEFAULT_DB_PATH, get_session
from tint_sis.routing import find_homologos_expert_pairs, find_homologos_master_pair


@dataclass
class PipelineSummary:
    ingestion_warnings: list[str] = field(default_factory=list)
    archivos_csv: list[Path] = field(default_factory=list)
    archivos_excel_passthrough: list[Path] = field(default_factory=list)


def run_pipeline(
    input_dir: Path,
    output_dir: Path,
    db_path: Path = DEFAULT_DB_PATH,
) -> PipelineSummary:
    """Cruza el archivo experto maestro (xData_DATACOMPLETA_<fecha>.xlsx) contra
    homologos_TINT.xlsx y genera, por cada tienda habilitada en ENABLED_GRUPOS,
    <grupo>_ready.xlsx + <grupo>_ready.csv en output_dir. Unico flujo del sistema
    (el piloto CorobLab/FORMULARIO se retiro; ver GUIA_USO.md)."""
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)

    summary = PipelineSummary()

    session = get_session(db_path)
    try:
        batch = repository.create_batch(session, origen_dir=str(input_dir))

        homologos_pairs = []
        master_pair = find_homologos_master_pair(input_dir)
        if master_pair is not None:
            homologos_pairs.append(master_pair)
        homologos_pairs.extend(find_homologos_expert_pairs(input_dir))

        for pair in homologos_pairs:
            results, warns = run_homologos_filter(pair.expert_path, pair.homologos_path, output_dir)
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

        session.commit()
    finally:
        session.close()

    return summary
