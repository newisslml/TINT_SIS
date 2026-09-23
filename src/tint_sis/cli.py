from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tint_sis.config import load_config
from tint_sis.expertos import EXPERTOS
from tint_sis.pipeline import run_pipeline
from tint_sis.routing import EXPERT_MASTER_GLOB, find_latest_expert


def _cmd_run(args, cfg) -> None:
    kwargs = {
        "input_dir": Path(args.input) if args.input else Path(cfg.input_dir),
        "output_dir": Path(args.output) if args.output else Path(cfg.output_dir),
        "db_path": Path(args.db) if args.db else Path(cfg.db_path),
        "enabled_grupos": set(cfg.enabled_grupos),
        "expertos_habilitados": set(cfg.expertos_habilitados),
        "productos_name": cfg.productos_name,
        "expertos_globs": cfg.expertos,
        "softwares": cfg.software_defs(),
        "filtrados_dirname": cfg.filtrados_dirname,
    }
    summary = run_pipeline(**kwargs)

    por_software: dict[str, list] = {}
    for gf in summary.archivos:
        por_software.setdefault(gf.software, []).append(gf)
    print(f"Archivos generados: {len(summary.archivos)}")
    for software, archivos in por_software.items():
        print(f"  {software}:")
        for gf in archivos:
            print(f"    - {gf.ruta}  ({gf.filas:,} filas)".replace(",", "."))

    if summary.ingestion_warnings:
        print("\nAdvertencias:")
        for w in summary.ingestion_warnings:
            print(f"  - {w}")


def _cmd_productos_init(args, cfg) -> None:
    from tint_sis.adapters.productos import bootstrap_tabla

    input_dir = Path(args.input) if args.input else Path(cfg.input_dir)
    expertos_dir = Path(args.expertos_dir) if args.expertos_dir else input_dir
    homologos = Path(args.homologos) if args.homologos else input_dir / cfg.homologos_master_name
    xdata = Path(args.xdata) if args.xdata else find_latest_expert(input_dir, EXPERT_MASTER_GLOB)
    destino = Path(args.salida) if args.salida else input_dir / cfg.productos_name

    if not homologos.exists():
        sys.exit(f"No se encontro {homologos}")
    if destino.exists() and not args.force:
        sys.exit(f"{destino} ya existe: no se sobreescribe (usar --force para regenerarla)")
    if destino.exists():
        destino.unlink()

    expertos = {
        label: find_latest_expert(expertos_dir, cfg.expertos.get(label, d.default_glob))
        for label, d in EXPERTOS.items()
    }
    print(f"Homologos: {homologos}")
    print(f"xData con ID_TINT: {xdata or '(no hay: Experto 3 se sugiere por nombre)'}")
    for label, path in expertos.items():
        print(f"{label}: {path or '(no hay)'}")

    resumen = bootstrap_tabla(homologos, xdata, expertos, destino, on_log=print)
    print(f"\nTabla generada: {resumen.destino}")
    print(f"  productos: {resumen.productos}  (a revisar: {resumen.a_revisar})")
    for label, n in resumen.sin_asignar.items():
        print(f"  {label}: {n} producto(s) sin asignar (ver hoja 'Sin asignar')")
    print("Revisala en Excel (columna 'Revisar' y hoja 'Sin asignar') antes de correr el ciclo.")


def main() -> None:
    parser = argparse.ArgumentParser(prog="tint_sis")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser(
        "run", help="Procesa un ciclo: expertos + tabla de productos -> archivos filtrados por software"
    )
    run_parser.add_argument("--input", default=None, help="carpeta de entrada (default: config)")
    # Carpeta base: los finales se guardan en <output>/Archivos filtrados/<Software>/.
    run_parser.add_argument("--output", default=None, help="carpeta base de salida (default: config)")
    run_parser.add_argument("--db", default=None)

    init_parser = subparsers.add_parser(
        "productos-init",
        help="Arma productos_TINT.xlsx una vez, desde homologos_TINT.xlsx + xData con ID_TINT + los expertos",
    )
    init_parser.add_argument("--input", default=None, help="carpeta de entrada (default: config)")
    init_parser.add_argument("--expertos-dir", default=None, help="donde buscar Experto_1/2/3 (default: --input)")
    init_parser.add_argument("--homologos", default=None, help="default: <input>/homologos_TINT.xlsx")
    init_parser.add_argument("--xdata", default=None, help="default: el xData_DATACOMPLETA*.xlsx mas nuevo de <input>")
    init_parser.add_argument("--salida", default=None, help="default: <input>/productos_TINT.xlsx")
    init_parser.add_argument("--force", action="store_true", help="regenerar aunque ya exista (pisa la revisada)")

    args = parser.parse_args()
    cfg = load_config()
    if args.command == "run":
        _cmd_run(args, cfg)
    elif args.command == "productos-init":
        _cmd_productos_init(args, cfg)


if __name__ == "__main__":
    main()
