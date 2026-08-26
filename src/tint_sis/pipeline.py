from __future__ import annotations

import shutil
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from tint_sis.adapters.ajuste_expert import write_ajuste_expert_file
from tint_sis.adapters.coroblab import write_coroblab_file
from tint_sis.adapters.homologos_filter import run_homologos_filter
from tint_sis.adapters.passthrough_csv import write_passthrough_csv
from tint_sis.canonical.models import FormulaCanonica
from tint_sis.db import repository
from tint_sis.db.database import DEFAULT_DB_PATH, get_session
from tint_sis.ingestion.excel_reader import read_batch
from tint_sis.routing import find_homologos_expert_pairs, parse_expert_filename
from tint_sis.validation.rules import ValidationIssue, validate_batch


@dataclass
class PipelineSummary:
    formulas_leidas: int = 0
    formulas_generadas: int = 0
    formulas_con_error: int = 0
    issues: list[ValidationIssue] = field(default_factory=list)
    ingestion_warnings: list[str] = field(default_factory=list)
    archivos_generados: list[Path] = field(default_factory=list)
    archivos_ajuste: list[Path] = field(default_factory=list)
    archivos_csv: list[Path] = field(default_factory=list)
    archivos_excel_passthrough: list[Path] = field(default_factory=list)


def run_pipeline(
    input_dir: Path,
    output_dir: Path,
    db_path: Path = DEFAULT_DB_PATH,
) -> PipelineSummary:
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)

    ingest_result = read_batch(input_dir)
    issues = validate_batch(ingest_result.formulas)
    errors_by_key = {
        (i.linea_producto, i.origen_archivo, i.origen_fila)
        for i in issues
        if i.severity == "error"
    }

    valid_formulas: list[FormulaCanonica] = [
        f for f in ingest_result.formulas
        if (f.linea_producto, f.origen_archivo, f.origen_fila) not in errors_by_key
    ]

    by_linea: dict[str, list[FormulaCanonica]] = defaultdict(list)
    for formula in valid_formulas:
        by_linea[formula.linea_producto].append(formula)

    summary = PipelineSummary(
        formulas_leidas=len(ingest_result.formulas),
        formulas_generadas=len(valid_formulas),
        formulas_con_error=len(ingest_result.formulas) - len(valid_formulas),
        issues=issues,
        ingestion_warnings=ingest_result.warnings,
    )

    session = get_session(db_path)
    try:
        batch = repository.create_batch(session, origen_dir=str(input_dir))
        repository.save_formulas(session, batch, ingest_result.formulas)
        repository.save_issues(session, batch, issues)

        for linea, formulas in by_linea.items():
            ajuste_path = output_dir / "ajuste" / f"filtrado_{linea}.xlsx"
            write_ajuste_expert_file(formulas, ajuste_path)
            summary.archivos_ajuste.append(ajuste_path)
            repository.record_generated_file(session, batch, linea, "ajuste_expert", str(ajuste_path))

            out_path = output_dir / f"{linea}.txt"
            write_coroblab_file(formulas, out_path)
            summary.archivos_generados.append(out_path)
            repository.record_generated_file(session, batch, linea, "coroblab", str(out_path))

        for path in sorted(input_dir.glob("*.xlsx")):
            route = parse_expert_filename(path)
            if route is None:
                continue
            linea = f"{route.grupo}_{route.maquina}"
            if route.formato_salida == "csv_passthrough":
                csv_path = output_dir / f"{path.stem}.csv"
                write_passthrough_csv(path, csv_path)
                summary.archivos_csv.append(csv_path)
                repository.record_generated_file(session, batch, linea, "csv_passthrough", str(csv_path))

                # Se pide tambien el excel en output (redundante con el input, pero
                # es uno de los 2 formatos de entrega para este grupo/maquina).
                excel_path = output_dir / path.name
                excel_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, excel_path)
                summary.archivos_excel_passthrough.append(excel_path)
                repository.record_generated_file(session, batch, linea, "excel_passthrough", str(excel_path))
            else:
                summary.ingestion_warnings.append(
                    f"{path.name}: la maquina '{route.maquina}' no tiene un formato de salida "
                    "registrado (agregar a MACHINE_OUTPUT_FORMATS en routing.py) - se omite"
                )

        for pair in find_homologos_expert_pairs(input_dir):
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
