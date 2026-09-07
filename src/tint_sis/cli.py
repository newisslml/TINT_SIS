from __future__ import annotations

import argparse
from pathlib import Path

from tint_sis.pipeline import run_pipeline

REPO_ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser(prog="tint_sis")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser(
        "run", help="Procesa un ciclo: experto xData + homologos -> archivos filtrados por tienda"
    )
    run_parser.add_argument("--input", default=str(REPO_ROOT / "data" / "input"))
    run_parser.add_argument("--output", default=str(REPO_ROOT / "data" / "output"))
    run_parser.add_argument("--db", default=None)

    args = parser.parse_args()

    if args.command == "run":
        db_path = Path(args.db) if args.db else None
        kwargs = {"input_dir": Path(args.input), "output_dir": Path(args.output)}
        if db_path:
            kwargs["db_path"] = db_path
        summary = run_pipeline(**kwargs)

        print(f"Archivos generados (CSV, formato completo): {len(summary.archivos_csv)}")
        for path in summary.archivos_csv:
            print(f"  - {path}")
        print(f"Archivos generados (Excel, formato completo): {len(summary.archivos_excel_passthrough)}")
        for path in summary.archivos_excel_passthrough:
            print(f"  - {path}")

        # Advertencias de ingesta: se siguen juntando en summary.ingestion_warnings
        # (pipeline.py), solo se deja de imprimir por ahora a pedido del usuario.
        # if summary.ingestion_warnings:
        #     print("\nAdvertencias de ingesta:")
        #     for w in summary.ingestion_warnings:
        #         print(f"  - {w}")


if __name__ == "__main__":
    main()
