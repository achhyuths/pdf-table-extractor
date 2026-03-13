"""
Core extraction logic: detect tables in SEC PDFs, extract headings, render cropped images.

Uses pdfplumber for table detection and PyMuPDF (fitz) for high-quality image rendering.
Tries multiple detection strategies to handle both line-based and text-based table layouts.
Falls back to full-page capture for presentation-style slides with financial data.
"""

import logging
import re
import warnings
from pathlib import Path

import fitz  # PyMuPDF
import pdfplumber

from src.utils import (
    build_image_filename,
    ensure_dirs,
    extract_heading_above_table,
    parse_period_from_filename,
)

# Suppress noisy pdfplumber warnings about invalid color values
logging.getLogger("pdfminer").setLevel(logging.ERROR)
warnings.filterwarnings("ignore", message=".*Cannot set.*non-stroke color.*")

# Minimum table height in points — filters out false detections in headers/footers
MIN_TABLE_HEIGHT = 25

# Image rendering DPI
RENDER_DPI = 225

# Padding around the table crop (in PDF points)
PAD_TOP = 50    # extra space above to capture heading
PAD_BOTTOM = 10
PAD_LEFT = 10
PAD_RIGHT = 10

# Table detection strategies to try, in order of preference
TABLE_STRATEGIES = [
    # Strategy 1: default (auto-detects lines/text)
    {},
    # Strategy 2: explicit text-based detection (for borderless tables)
    {
        "vertical_strategy": "text",
        "horizontal_strategy": "text",
        "snap_y_tolerance": 5,
        "intersection_x_tolerance": 15,
    },
    # Strategy 3: text with looser tolerances
    {
        "vertical_strategy": "text",
        "horizontal_strategy": "text",
        "snap_y_tolerance": 8,
        "snap_x_tolerance": 8,
        "intersection_x_tolerance": 20,
        "min_words_vertical": 2,
        "min_words_horizontal": 2,
    },
]

# Financial keywords that indicate a page contains tabular financial data
FINANCIAL_KEYWORDS = [
    r"revenue", r"margin", r"income", r"earnings", r"cash\s+flow",
    r"ebitda", r"gross\s+profit", r"operating", r"balance\s+sheet",
    r"production", r"deliveries", r"capacity", r"deployments",
    r"gaap", r"non-gaap", r"eps", r"free\s+cash", r"capital\s+expenditures",
    r"inventory", r"assets", r"liabilities", r"depreciation",
    r"summary", r"financial\s+statement", r"highlights",
]

# Pages to skip (boilerplate SEC pages)
SKIP_PAGE_PATTERNS = [
    r"UNITED\s+STATES\s+SECURITIES",
    r"SIGNATURES\s+Pursuant",
    r"Item\s+\d+\.\d+\s+Results",
    r"Pursuant\s+to\s+Section\s+13",
]

# Headings that indicate a detected table is actually boilerplate (not real financial data)
BOILERPLATE_HEADINGS = [
    r"^Table\s+of\s+Contents$",
    r"^SIGNATURES$",
]


def _table_has_numeric_data(table) -> bool:
    """Check if a detected table actually contains numeric data (not just prose)."""
    try:
        data = table.extract()
        if not data:
            return False
        # Check if at least some cells contain numbers
        num_cells = 0
        total_cells = 0
        for row in data:
            for cell in row:
                if cell is not None:
                    total_cells += 1
                    # Cell contains a number (integer, decimal, percentage, dollar amount)
                    if re.search(r'\d', str(cell)):
                        num_cells += 1
        # At least 20% of non-empty cells should have numbers for a financial table
        return total_cells > 0 and (num_cells / total_cells) >= 0.2
    except Exception:
        return False


def _find_tables_multi_strategy(page) -> list:
    """
    Try multiple table detection strategies on a page.

    Uses default strategy first (high confidence). Only falls back to text-based
    strategies if default finds nothing, and validates that text-detected tables
    actually contain numeric data to avoid false positives on prose pages.
    """
    # Strategy 1: default (auto-detects lines/borders) — high confidence
    try:
        tables = page.find_tables()
        if tables:
            return tables
    except Exception:
        pass

    # Strategy 2-3: text-based fallbacks — only accept if tables contain numbers
    for settings in TABLE_STRATEGIES[1:]:
        try:
            tables = page.find_tables(table_settings=settings)
            if tables:
                valid = [t for t in tables if _table_has_numeric_data(t)]
                if valid:
                    return valid
        except Exception:
            continue

    return []


def _page_has_financial_content(page_text: str) -> bool:
    """Check if page text contains financial/tabular keywords."""
    lower = page_text.lower()
    matches = sum(1 for kw in FINANCIAL_KEYWORDS if re.search(kw, lower))
    return matches >= 2


def _is_boilerplate_page(page_text: str) -> bool:
    """Check if page is a SEC boilerplate page (cover, signatures, prose, etc.)."""
    for pattern in SKIP_PAGE_PATTERNS:
        if re.search(pattern, page_text[:500]):
            return True
    # Skip 10-K/10-Q narrative pages that start with "Table of Contents"
    # These are prose pages with a header, not actual financial tables
    if page_text.strip().startswith("Table of Contents"):
        return True
    # Skip pages that are mostly prose (SEC Part headers, Items, etc.)
    if re.match(r"^(PART\s+[IVX]+|Item\s+\d)", page_text.strip()[:20], re.IGNORECASE):
        return True
    return False


def _extract_page_title(page_text: str) -> str:
    """
    Extract a title from the beginning of page text for presentation slides.
    Looks for spaced-out headings like 'F I N A N C I A L  S U M M A R Y'.
    """
    # Split into lines (some slides have all text as one blob with tabs)
    lines = page_text.replace("\t", "\n").split("\n")

    for line in lines[:5]:
        text = line.strip()
        if not text or len(text) < 5:
            continue
        # Skip lines that are purely numeric or just page numbers
        if re.match(r"^[\d\s\.\,\$%\-]+$", text):
            continue
        # Found a real title line — take up to 80 chars
        return text[:80]

    return ""


def extract_tables_from_pdf(
    pdf_path: Path,
    company: str,
    output_dir: Path,
) -> list[dict]:
    """
    Extract all tables from a single PDF.

    Args:
        pdf_path: path to the PDF file
        company: company ticker (e.g. "TSLA")
        output_dir: directory to save cropped table images

    Returns:
        List of metadata dicts, one per table found.
    """
    report_name = pdf_path.stem  # e.g. "TSLA-Q3-2025-Update"
    period = parse_period_from_filename(pdf_path.name)

    tables_metadata = []

    # Open with both libraries
    plumber_pdf = pdfplumber.open(pdf_path)
    fitz_doc = fitz.open(pdf_path)

    try:
        for page_idx, plumber_page in enumerate(plumber_pdf.pages):
            page_num = page_idx + 1
            page_width = plumber_page.width
            page_height = plumber_page.height

            # Detect tables using multi-strategy approach
            found_tables = _find_tables_multi_strategy(plumber_page)

            # Get the corresponding fitz page for rendering
            fitz_page = fitz_doc[page_idx]

            if found_tables:
                # --- Standard table extraction ---
                for tbl_idx, table in enumerate(found_tables):
                    bbox = table.bbox  # (x0, y0, x1, y1) in pdfplumber coords
                    x0, y0, x1, y1 = bbox

                    # Filter out tiny "tables" (likely false positives)
                    table_height = y1 - y0
                    if table_height < MIN_TABLE_HEIGHT:
                        continue

                    # Extract heading
                    heading = extract_heading_above_table(plumber_page, bbox)
                    if not heading:
                        heading = f"Unknown Table (Page {page_num}, Table {tbl_idx + 1})"

                    # Extract raw table data
                    raw_data = table.extract()
                    num_rows = len(raw_data) if raw_data else 0
                    num_cols = len(raw_data[0]) if raw_data and raw_data[0] else 0

                    # Render cropped image with PyMuPDF
                    crop_x0 = max(0, x0 - PAD_LEFT)
                    crop_y0 = max(0, y0 - PAD_TOP)
                    crop_x1 = min(page_width, x1 + PAD_RIGHT)
                    crop_y1 = min(page_height, y1 + PAD_BOTTOM)

                    clip_rect = fitz.Rect(crop_x0, crop_y0, crop_x1, crop_y1)
                    zoom = RENDER_DPI / 72
                    mat = fitz.Matrix(zoom, zoom)
                    pix = fitz_page.get_pixmap(matrix=mat, clip=clip_rect)

                    img_filename = build_image_filename(company, report_name, page_num, tbl_idx + 1)
                    img_path = output_dir / img_filename
                    pix.save(str(img_path))

                    rel_img_path = str(Path("data") / "extracted_tables" / company / img_filename)

                    tables_metadata.append({
                        "company": company,
                        "report_name": report_name,
                        "period": period,
                        "page_number": page_num,
                        "table_index": tbl_idx + 1,
                        "heading": heading,
                        "image_path": rel_img_path,
                        "num_rows": num_rows,
                        "num_cols": num_cols,
                        "bbox_x0": round(x0, 1),
                        "bbox_y0": round(y0, 1),
                        "bbox_x1": round(x1, 1),
                        "bbox_y1": round(y1, 1),
                    })

            else:
                # --- Fallback: full-page capture for presentation slides ---
                page_text = plumber_page.extract_text() or ""
                if not page_text.strip():
                    continue
                if _is_boilerplate_page(page_text):
                    continue
                if not _page_has_financial_content(page_text):
                    continue

                # This page has financial data but no detectable tables —
                # capture the full page as a table image
                title = _extract_page_title(page_text)
                if not title:
                    title = f"Financial Data (Page {page_num})"

                # Render the full page
                zoom = RENDER_DPI / 72
                mat = fitz.Matrix(zoom, zoom)
                pix = fitz_page.get_pixmap(matrix=mat)

                img_filename = build_image_filename(company, report_name, page_num, 1)
                img_path = output_dir / img_filename
                pix.save(str(img_path))

                rel_img_path = str(Path("data") / "extracted_tables" / company / img_filename)

                # Estimate rows/cols from text content
                text_lines = [l for l in page_text.split("\n") if l.strip()]
                num_rows = len(text_lines)
                # Estimate columns from tab-separated content
                if text_lines:
                    max_tabs = max(line.count("\t") for line in text_lines)
                    num_cols = max_tabs + 1
                else:
                    num_cols = 0

                tables_metadata.append({
                    "company": company,
                    "report_name": report_name,
                    "period": period,
                    "page_number": page_num,
                    "table_index": 1,
                    "heading": title,
                    "image_path": rel_img_path,
                    "num_rows": num_rows,
                    "num_cols": num_cols,
                    "bbox_x0": 0,
                    "bbox_y0": 0,
                    "bbox_x1": round(page_width, 1),
                    "bbox_y1": round(page_height, 1),
                })

    finally:
        plumber_pdf.close()
        fitz_doc.close()

    return tables_metadata


def process_company_folder(
    company_folder: Path,
    project_root: Path,
) -> list[dict]:
    """
    Process all PDFs in a company folder.

    Args:
        company_folder: path to e.g. data/raw_pdfs/TSLA/
        project_root: root of the project (for output paths)

    Returns:
        Combined list of table metadata across all PDFs for this company.
    """
    company = company_folder.name  # e.g. "TSLA"
    dirs = ensure_dirs(project_root, company)
    output_dir = dirs["extracted"]

    all_metadata = []
    pdf_files = sorted(company_folder.glob("*.pdf"))

    if not pdf_files:
        print(f"  No PDF files found in {company_folder}")
        return all_metadata

    for pdf_path in pdf_files:
        print(f"  Processing {company}/{pdf_path.name}...", end=" ", flush=True)
        try:
            metadata = extract_tables_from_pdf(pdf_path, company, output_dir)
            all_metadata.extend(metadata)
            print(f"Found {len(metadata)} tables")
        except Exception as e:
            print(f"ERROR: {e}")

    return all_metadata
