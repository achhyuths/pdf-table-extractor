"""
Simple helpers for the PDF table extractor.
"""

import re
from pathlib import Path


def extract_heading_above_table(page, table_bbox):
    """
    Get the heading text above a table.

    Looks at the text just above the table's top edge and returns
    the first line that looks like a real title (not just numbers or dates).
    """
    x0, y0, x1, y1 = table_bbox

    # Get the text from the area above the table
    # Look up to 100 points above the table top
    crop_top = max(0, y0 - 100)
    crop_box = (x0, crop_top, x1, y0)

    try:
        cropped = page.within_bbox(crop_box)
        text = cropped.extract_text() or ""
    except Exception:
        return ""

    if not text.strip():
        return ""

    # Split into lines and go from bottom to top (closest to table first)
    lines = [line.strip() for line in text.strip().split("\n") if line.strip()]
    lines.reverse()

    for line in lines:
        # Skip lines that are just numbers, dates, dollar signs, etc.
        if re.match(r'^[\s\d,\$%\.\-\/]+$', line):
            continue
        # Skip very short lines (page numbers, etc.)
        if len(line) < 5:
            continue
        # Skip lines that look like column headers (just years)
        if re.match(r'^[\d\s]+$', line):
            continue
        # This looks like a real heading
        return line

    return ""


def parse_period_from_filename(filename):
    """
    Try to get a period like 'Q1-2025' from a PDF filename.

    Examples:
        'TSLA-Q3-2025-Update.pdf' -> 'Q3-2025'
        'TSLA-Annual-2024.pdf' -> 'Annual-2024'
        'some-random.pdf' -> ''
    """
    # Look for Q1-2025, Q2-2024 etc.
    match = re.search(r"(Q[1-4][-_]\d{4})", filename, re.IGNORECASE)
    if match:
        return match.group(1).upper().replace("_", "-")

    # Look for Annual/FY patterns
    match = re.search(r"((?:Annual|FY)[-_]\d{4})", filename, re.IGNORECASE)
    if match:
        return match.group(1).replace("_", "-")

    # Look for just a year
    match = re.search(r"(20\d{2})", filename)
    if match:
        return match.group(1)

    return ""


def build_image_filename(company, report_name, page_num, table_idx):
    """
    Build a standardized image filename.
    Example: TSLA_Q3-2025-Update_p04_t01.png
    """
    return f"{company}_{report_name}_p{page_num:02d}_t{table_idx:02d}.png"


def ensure_dirs(base_path, company):
    """Create output directories if they don't exist and return their paths."""
    extracted_dir = base_path / "data" / "extracted_tables" / company
    index_dir = base_path / "data" / "index"
    extracted_dir.mkdir(parents=True, exist_ok=True)
    index_dir.mkdir(parents=True, exist_ok=True)
    return {"extracted": extracted_dir, "index": index_dir}
