"""cli.py — Interfaz de línea de comandos para el pipeline de tributación.

Punto de entrada registrado como ``tributacion-run`` en ``pyproject.toml``.

Uso
---
::

    tributacion-run \\
        --pdf "Plan de Estudios Informática Julio 2025.pdf" \\
        --matrix "Matriz de Tributación Informática 14.11 (1).xlsx" \\
        --output tributacion_final.xlsx \\
        --sheet "Asignaturas - RA"

Argumentos
----------
--pdf       Ruta al PDF del plan de estudio (obligatorio).
--matrix    Ruta al Excel de la Matriz de Tributación (obligatorio).
--output    Ruta de destino para el Excel de salida.
            Por defecto: ``tributacion_final.xlsx``.
--sheet     Nombre de la hoja en la matriz.
            Por defecto: ``"Asignaturas - RA"``.
--verbose   Activa el logging detallado (DEBUG).
"""

import argparse
import logging
import sys
from pathlib import Path

from tributacion.pipeline import run_pipeline


def _build_parser() -> argparse.ArgumentParser:
    """Construye y retorna el parser de argumentos."""
    parser = argparse.ArgumentParser(
        prog="tributacion-run",
        description=(
            "Pipeline de tributación curricular: "
            "PDF del plan de estudio + Matriz Excel → Excel de tributación."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--pdf",
        required=True,
        type=Path,
        metavar="PDF",
        help="Ruta al PDF del plan de estudio de la carrera.",
    )
    parser.add_argument(
        "--matrix",
        required=True,
        type=Path,
        metavar="XLSX",
        help="Ruta al Excel de la Matriz de Tributación.",
    )
    parser.add_argument(
        "--output",
        default=Path("tributacion_final.xlsx"),
        type=Path,
        metavar="XLSX",
        help="Ruta de destino del Excel de salida. (default: tributacion_final.xlsx)",
    )
    parser.add_argument(
        "--sheet",
        default="Asignaturas - RA",
        metavar="HOJA",
        help="Nombre de la hoja en la Matriz de Tributación. (default: 'Asignaturas - RA')",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Activa el logging detallado.",
    )
    return parser


def main() -> None:
    """Punto de entrada principal del CLI ``tributacion-run``."""
    parser = _build_parser()
    args = parser.parse_args()

    # Configurar logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
        level=level,
        stream=sys.stderr,
    )

    # Validar existencia de archivos de entrada antes de correr el pipeline
    for attr, label in [("pdf", "PDF"), ("matrix", "Matriz Excel")]:
        path: Path = getattr(args, attr)
        if not path.exists():
            logging.error("%s no encontrado: %s", label, path)
            sys.exit(1)

    try:
        df = run_pipeline(
            pdf_path=args.pdf,
            matrix_xlsx=args.matrix,
            output_xlsx=args.output,
            sheet_name=args.sheet,
        )
        print(
            f"\nOK — {len(df)} filas × {len(df.columns)} columnas → {args.output}"
        )
    except Exception as exc:
        logging.error("Error durante el pipeline: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
