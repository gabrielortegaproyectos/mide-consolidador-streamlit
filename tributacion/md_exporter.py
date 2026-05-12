"""md_exporter.py — Exportación de planes PDF a documentos Markdown.

Genera un ``.md`` por carrera/opción que representa fielmente el contenido
completo del PDF:

- **Páginas sin tabla de horas** → texto + tablas raw extraídas con PyMuPDF,
  preservando la estructura visual de la página (títulos en mayúsculas
  cortas promovidos a encabezado ``##``).
- **Páginas con tabla de horas** → tabla estructurada por semestre usando el
  parser vigente (:func:`~tributacion.pdf_parser.extract_table_rows`), con
  columnas limpias y encabezado ``## Semestre N``.

Cuando el PDF contiene variantes académicas (detectadas por
:func:`~tributacion.pdf_parser._split_by_option`), se genera un documento
por variante; cada documento filtra las páginas de horas por su opción y
conserva todas las páginas de texto/contexto.
"""

from __future__ import annotations

import logging
import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pymupdf

from tributacion.config import TARGET_TEXT
from tributacion.pdf_parser import (
    _split_by_option,
    build_col_map,
    extract_table_rows,
    find_header_row,
    parse_pdf,
)
from tributacion.plan_catalog import PlanCatalogEntry, REPO_ROOT, load_plan_catalog
from tributacion.text_utils import detect_option_from_rows, detect_semester_from_rows, detect_semester_from_text

logger = logging.getLogger(__name__)

DEFAULT_MD_OUTPUT_DIR = REPO_ROOT / "data" / "md_documents"

# Columnas a mostrar en las tablas de horas (fuente y CARRERA son redundantes
# dado que ya constan en el encabezado del documento).
_HOURS_DISPLAY_COLUMNS: list[str] = [
    "codigo_prerrequisito",
    "asignatura_prerrequisito",
    "codigo",
    "asignatura",
    "sct",
    "horas_docencia_directa",
    "DD TEÓRICAS",
    "DD AYUDANTÍA",
    "DD TALLER",
    "DD CAMPOS CLÍNICOS",
    "DD SIMULACIÓN",
    "DD LABORATORIO",
    "DD PRO COLABORATIVO",
    "DD SALIDAS A TERRENO",
    "total_trabajo_autonomo",
    "total_plan_estudio",
]


# ---------------------------------------------------------------------------
# Utilidades compartidas
# ---------------------------------------------------------------------------

def _safe_dirname(name: str) -> str:
    """Convierte un texto en un nombre seguro para archivo/directorio."""
    upper_name = name.upper().replace(" ", "_")
    return re.sub(r"[^\w\-]", "", upper_name)


def _variant_carrera_name(carrera: str, option_label: str | None) -> str:
    """Construye el nombre lógico de carrera considerando variantes."""
    if option_label is None:
        return carrera
    return f"{carrera}-{_safe_dirname(option_label)}"


def _display_path(path: Path) -> str:
    """Retorna una representación estable de ruta para logging."""
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _escape_cell(value: object) -> str:
    """Escapa caracteres problemáticos para celdas de tabla Markdown."""
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ").strip()


# ---------------------------------------------------------------------------
# Renderizado de páginas de TEXTO (sin tabla de horas)
# ---------------------------------------------------------------------------

def _raw_table_to_markdown(table) -> str:
    """Convierte un objeto ``Table`` de PyMuPDF a tabla Markdown en bruto."""
    rows = table.extract()
    if not rows:
        return ""
    lines: list[str] = []
    header = [str(c or "").replace("\n", " ").strip() for c in rows[0]]
    lines.append("| " + " | ".join(_escape_cell(h) for h in header) + " |")
    lines.append("| " + " | ".join("---" for _ in header) + " |")
    for row in rows[1:]:
        cells = [_escape_cell(c) for c in row]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _text_page_to_markdown(page, page_num: int) -> str:
    """Renderiza una página PDF sin tabla de horas a Markdown.

    Detecta los rectángulos de las tablas y evita duplicar su texto en los
    bloques de texto. Las líneas cortas en mayúsculas se promueven a ``##``.
    Tablas y texto se reordenan por posición vertical para respetar el layout.

    Args:
        page:     Objeto ``pymupdf.Page``.
        page_num: Número de página 1-basado.

    Returns:
        Cadena Markdown de la página.
    """
    parts: list[str] = [f"---\n\n<!-- Página {page_num} -->"]

    tab_finder = page.find_tables()
    tables = tab_finder.tables if tab_finder else []
    table_rects = [t.bbox for t in tables]

    blocks: list[tuple[float, str, str]] = []

    for block in page.get_text("blocks", sort=True):
        x0, y0, x1, y1, text, *_ = block
        text = text.strip()
        if not text:
            continue
        overlaps = any(
            x0 < tx1 and x1 > tx0 and y0 < ty1 and y1 > ty0
            for tx0, ty0, tx1, ty1 in table_rects
        )
        if not overlaps:
            blocks.append((y0, "text", text))

    for table in tables:
        raw_md = _raw_table_to_markdown(table)
        if raw_md:
            blocks.append((table.bbox[1], "table", raw_md))

    blocks.sort(key=lambda b: b[0])

    for _, kind, content in blocks:
        if kind == "text":
            stripped = content.strip()
            if stripped and len(stripped) < 100 and stripped.replace(" ", "").isupper():
                parts.append(f"## {stripped}")
            else:
                parts.append(stripped)
        else:
            parts.append(content)

    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Renderizado de páginas de HORAS (tabla estructurada)
# ---------------------------------------------------------------------------

def _hours_page_to_markdown(
    rows: list[list],
    col_map: dict[str, int],
    fuente: str,
    carrera: str,
    semestre: int,
    option_label: str | None,
    page_num: int,
) -> str:
    """Renderiza la tabla de horas de una página a Markdown estructurado.

    Usa las mismas funciones de extracción del parser vigente y produce una
    tabla Markdown con columnas limpias bajo el encabezado de semestre.

    Args:
        rows:         Filas extraídas con ``Table.extract()``.
        col_map:      Mapa campo→índice de ``build_col_map()``.
        fuente:       Nombre del archivo PDF (sin extensión).
        carrera:      Nombre de la carrera.
        semestre:     Número de semestre detectado.
        option_label: Etiqueta de variante o ``None``.
        page_num:     Número de página 1-basado.

    Returns:
        Cadena Markdown de la sección de semestre, o cadena vacía si sin datos.
    """
    records = extract_table_rows(rows, col_map, fuente, carrera, semestre, option_label)
    if not records:
        return ""

    # Encabezado de semestre: busca celda que contenga un ordinal explícito
    # (primer, segundo…) usando detect_semester_from_text para evitar capturar
    # frases genéricas como "distribución y cálculo… por semestre".
    sem_label = f"Semestre {semestre}"
    for row in rows[:6]:
        for cell in row:
            text = str(cell or "").strip()
            if text and detect_semester_from_text(text) != 0:
                sem_label = text.replace("\n", " ").strip()
                break
        else:
            continue
        break

    heading = f"## {sem_label}"
    if option_label:
        heading += f" — {option_label}"

    separator = f"---\n\n<!-- Página {page_num} (horas) -->"

    header_row = "| N° | " + " | ".join(_HOURS_DISPLAY_COLUMNS) + " |"
    sep_row = "| --- | " + " | ".join("---" for _ in _HOURS_DISPLAY_COLUMNS) + " |"
    table_lines = [header_row, sep_row]

    for idx, rec in enumerate(records, 1):
        values = [_escape_cell(rec.get(col, "")) for col in _HOURS_DISPLAY_COLUMNS]
        table_lines.append(f"| {idx} | " + " | ".join(values) + " |")

    return "\n\n".join([separator, heading, "\n".join(table_lines)])


# ---------------------------------------------------------------------------
# Conversión completa de PDF a Markdown
# ---------------------------------------------------------------------------

def render_pdf_as_markdown(
    pdf_path: Path,
    carrera: str,
    option_filter: str | None = None,
    include_all_options: bool = True,
) -> str:
    """Convierte todas las páginas de un PDF a Markdown.

    - Páginas sin tabla de horas → texto y tablas raw.
    - Páginas con tabla de horas → tabla estructurada con encabezado de semestre.

    Cuando ``include_all_options`` es ``False``, las páginas cuya etiqueta de
    opción no coincida con ``option_filter`` (ni sean base sin etiqueta) se omiten.

    Args:
        pdf_path:            Ruta al PDF.
        carrera:             Nombre de la carrera.
        option_filter:       Etiqueta de opción a incluir, o ``None`` para base.
        include_all_options: Si ``True``, incluye todas las opciones/variantes.

    Returns:
        Contenido Markdown de todas las páginas del PDF.
    """
    fuente = pdf_path.stem
    doc = pymupdf.open(str(pdf_path))
    sections: list[str] = []

    for page_num, page in enumerate(doc, 1):
        is_hours_page = TARGET_TEXT in page.get_text().lower()

        if not is_hours_page:
            sections.append(_text_page_to_markdown(page, page_num))
            continue

        # Página de distribución de horas → parser estructurado
        tab_finder = page.find_tables()
        if not tab_finder or not tab_finder.tables:
            sections.append(_text_page_to_markdown(page, page_num))
            continue

        main_table = max(tab_finder.tables, key=lambda t: len(t.extract()))
        rows = main_table.extract()

        semestre = detect_semester_from_rows(rows)
        option_label = detect_option_from_rows(rows)

        # Filtrar páginas de otras variantes cuando aplica
        if not include_all_options:
            page_is_base = option_label is None
            page_matches = option_label == option_filter
            if not page_is_base and not page_matches:
                continue

        hidx, header_row_data = find_header_row(rows)
        if hidx == -1:
            sections.append(_text_page_to_markdown(page, page_num))
            continue

        col_map = build_col_map(header_row_data)
        if not col_map:
            sections.append(_text_page_to_markdown(page, page_num))
            continue

        md_section = _hours_page_to_markdown(
            rows, col_map, fuente, carrera, semestre, option_label, page_num
        )
        sections.append(md_section if md_section else _text_page_to_markdown(page, page_num))

    doc.close()
    return "\n\n".join(s for s in sections if s)


def render_markdown_document(
    pdf_path: Path,
    carrera: str,
    pdf_rel_path: str,
    option_label: str | None,
    option_filter: str | None = None,
    include_all_options: bool = True,
) -> str:
    """Genera el documento Markdown completo para una carrera/opción.

    Añade encabezado con metadatos y delega la conversión página a página a
    :func:`render_pdf_as_markdown`.

    Args:
        pdf_path:            Ruta al PDF.
        carrera:             Nombre de la carrera base.
        pdf_rel_path:        Ruta relativa del PDF (catálogo).
        option_label:        Etiqueta de esta variante o ``None`` (BASE).
        option_filter:       Etiqueta a filtrar en páginas de horas.
        include_all_options: Si ``True``, no filtra por variante.

    Returns:
        Contenido Markdown completo.
    """
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    variant_name = _variant_carrera_name(carrera, option_label)

    header = "\n".join([
        f"# {variant_name}",
        "",
        "---",
        "",
        f"**Carrera base:** {carrera}  ",
        f"**Opción académica:** {option_label or 'BASE'}  ",
        f"**PDF origen:** `{pdf_rel_path}`  ",
        f"**Generado en:** {generated_at}  ",
        "",
        "---",
        "",
    ])

    body = render_pdf_as_markdown(
        pdf_path=pdf_path,
        carrera=carrera,
        option_filter=option_filter,
        include_all_options=include_all_options,
    )

    return header + body + "\n"


# ---------------------------------------------------------------------------
# Renderizado solo-tablas (versión compacta)
# ---------------------------------------------------------------------------

def render_tables_only_document(
    df_horas,
    carrera: str,
    pdf_rel_path: str,
    option_label: str | None,
) -> str:
    """Genera un documento Markdown con únicamente las tablas de horas por semestre.

    Produce una versión compacta: YAML-style header + una sección
    ``## Semestre N`` por semestre con tabla estructurada.  No incluye el
    contenido de páginas de texto (portada, perfil, etc.).

    Args:
        df_horas:     DataFrame resultado de :func:`~tributacion.pdf_parser.parse_pdf`
                      (ya filtrado por variante si corresponde).
        carrera:      Nombre de la carrera base.
        pdf_rel_path: Ruta relativa del PDF (catálogo).
        option_label: Etiqueta de esta variante o ``None`` (BASE).

    Returns:
        Contenido Markdown completo del documento.
    """
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    variant_name = _variant_carrera_name(carrera, option_label)

    header = "\n".join([
        f"# {variant_name}",
        "",
        "---",
        "",
        f"**Carrera base:** {carrera}  ",
        f"**Opción académica:** {option_label or 'BASE'}  ",
        f"**PDF origen:** `{pdf_rel_path}`  ",
        f"**Generado en:** {generated_at}  ",
        "",
        "---",
        "",
    ])

    if df_horas is None or df_horas.empty:
        return header + "_Sin datos de horas._\n"

    sections: list[str] = []
    semestres = sorted(df_horas["semestre"].dropna().unique())

    for sem in semestres:
        sem_df = df_horas[df_horas["semestre"] == sem]

        # Intentar recuperar etiqueta ordinal del propio DataFrame
        sem_label = f"Semestre {int(sem)}"
        if "semestre_texto" in df_horas.columns:
            texto_vals = sem_df["semestre_texto"].dropna().unique()
            for tv in texto_vals:
                if detect_semester_from_text(str(tv)) != 0:
                    sem_label = str(tv).replace("\n", " ").strip()
                    break

        heading = f"## {sem_label}"
        if option_label:
            heading += f" — {option_label}"

        # Columnas disponibles (intersección con las deseadas, en orden)
        display_cols = [c for c in _HOURS_DISPLAY_COLUMNS if c in df_horas.columns]
        header_row = "| N° | " + " | ".join(display_cols) + " |"
        sep_row = "| --- | " + " | ".join("---" for _ in display_cols) + " |"
        table_lines = [header_row, sep_row]

        for idx, (_, row) in enumerate(sem_df.iterrows(), 1):
            values = [_escape_cell(row.get(col, "")) for col in display_cols]
            table_lines.append(f"| {idx} | " + " | ".join(values) + " |")

        sections.append("\n\n".join([heading, "\n".join(table_lines)]))

    body = "\n\n".join(sections) if sections else "_Sin datos de horas._"
    return header + body + "\n"


# ---------------------------------------------------------------------------
# Limpieza del directorio de salida
# ---------------------------------------------------------------------------

def _clean_output_dir(output_dir: Path) -> None:
    """Elimina y recrea el directorio de salida."""
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Orquestador principal
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MarkdownExportSummary:
    """Resumen de una corrida de exportación Markdown."""

    generated_files: tuple[Path, ...]
    errors: tuple[str, ...]


def export_markdown_documents(
    output_dir: Path = DEFAULT_MD_OUTPUT_DIR,
    clean_output: bool = True,
    plans: list[PlanCatalogEntry] | None = None,
) -> MarkdownExportSummary:
    """Procesa todos los planes del catálogo y genera documentos Markdown.

    Produce **dos subconjuntos** de documentos dentro de ``output_dir``:

    - ``full/``   — Versión completa: todas las páginas del PDF (texto + horas)
      renderizadas fielmente página a página.
    - ``tables/`` — Versión compacta: únicamente las tablas de horas agrupadas
      por semestre, sin páginas de texto.

    Para cada entrada del catálogo:

    1. Parsea el PDF con :func:`~tributacion.pdf_parser.parse_pdf` para detectar
       variantes académicas mediante :func:`~tributacion.pdf_parser._split_by_option`.
    2. Carreras sin variantes → un único ``.md`` por versión.
    3. Carreras con variantes → un ``.md`` por opción y por versión.

    Args:
        output_dir:   Carpeta raíz de salida (default: ``data/md_documents``).
        clean_output: Si ``True``, borra ambas subcarpetas antes de exportar.
        plans:        Lista opcional de planes (tests o ejecución parcial).

    Returns:
        :class:`MarkdownExportSummary` con rutas generadas y errores.
    """
    resolved_output_dir = output_dir.resolve()
    full_dir = resolved_output_dir / "full"
    tables_dir = resolved_output_dir / "tables"

    if clean_output:
        _clean_output_dir(full_dir)
        _clean_output_dir(tables_dir)
    else:
        full_dir.mkdir(parents=True, exist_ok=True)
        tables_dir.mkdir(parents=True, exist_ok=True)

    loaded_plans = plans if plans is not None else load_plan_catalog()
    generated_files: list[Path] = []
    errors: list[str] = []
    used_names: dict[str, int] = {}

    for plan in loaded_plans:
        if not plan.pdf_path.exists():
            error = f"[ARCHIVO FALTANTE] {plan.carrera}: PDF no encontrado: {plan.pdf_path.name}"
            logger.warning(error)
            errors.append(error)
            continue

        try:
            df_full = parse_pdf(plan.pdf_path)
        except Exception as exc:  # noqa: BLE001
            error = f"[ERROR PDF] {plan.carrera}: {exc}"
            logger.error(error, exc_info=True)
            errors.append(error)
            continue

        variant_list = _split_by_option(df_full)
        has_variants = len(variant_list) > 1 or (
            len(variant_list) == 1 and variant_list[0][0] is not None
        )

        for option_label, variant_df in variant_list:
            variant_name = _variant_carrera_name(plan.carrera, option_label)
            safe_name = _safe_dirname(variant_name)
            count = used_names.get(safe_name, 0)
            used_names[safe_name] = count + 1
            if count > 0:
                safe_name = f"{safe_name}_{count + 1}"

            # -- versión full (todas las páginas) --
            try:
                full_content = render_markdown_document(
                    pdf_path=plan.pdf_path,
                    carrera=plan.carrera,
                    pdf_rel_path=plan.pdf_rel_path,
                    option_label=option_label,
                    option_filter=option_label,
                    include_all_options=not has_variants,
                )
                full_path = full_dir / f"{safe_name}.md"
                full_path.write_text(full_content, encoding="utf-8")
                generated_files.append(full_path)
                logger.info("[full]   %s", _display_path(full_path))
            except Exception as exc:  # noqa: BLE001
                error = f"[ERROR FULL] {variant_name}: {exc}"
                logger.error(error, exc_info=True)
                errors.append(error)

            # -- versión tables (solo tablas de horas) --
            try:
                tables_content = render_tables_only_document(
                    df_horas=variant_df,
                    carrera=plan.carrera,
                    pdf_rel_path=plan.pdf_rel_path,
                    option_label=option_label,
                )
                tables_path = tables_dir / f"{safe_name}.md"
                tables_path.write_text(tables_content, encoding="utf-8")
                generated_files.append(tables_path)
                logger.info("[tables] %s", _display_path(tables_path))
            except Exception as exc:  # noqa: BLE001
                error = f"[ERROR TABLES] {variant_name}: {exc}"
                logger.error(error, exc_info=True)
                errors.append(error)

    report_path = resolved_output_dir / "export_report.txt"
    report_lines = [
        f"Documentos generados: {len(generated_files)}",
        f"Errores: {len(errors)}",
        "",
    ]
    report_lines.extend(f"[OK] {path.relative_to(resolved_output_dir)}" for path in generated_files)
    if errors:
        report_lines.append("")
        report_lines.extend(errors)
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    return MarkdownExportSummary(
        generated_files=tuple(generated_files),
        errors=tuple(errors),
    )


__all__ = [
    "DEFAULT_MD_OUTPUT_DIR",
    "MarkdownExportSummary",
    "export_markdown_documents",
    "render_markdown_document",
    "render_pdf_as_markdown",
    "render_tables_only_document",
]
