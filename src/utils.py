"""
Simple helpers for the PDF table extractor.
"""

import re
from pathlib import Path


def extract_heading_above_table(page, table_bbox):
    """
    Get the heading text above a table.

    Crops a strip above the table and walks up from the bottom,
    skipping lines that are just numbers/years/dates (column headers).
    """
    x0, y0, x1, y1 = table_bbox

    # Crop a strip above the table (80 points tall, full page width)
    crop_top = max(0, y0 - 80)
    crop_box = (0, crop_top, page.width, y0)

    try:
        cropped = page.within_bbox(crop_box)
        text = cropped.extract_text() or ""
    except Exception:
        return ""

    # Walk lines from bottom to top (closest to table first)
    lines = [line.strip() for line in text.strip().split("\n") if line.strip()]
    lines.reverse()

    for line in lines:
        # Skip short lines (page numbers etc.)
        if len(line) < 5:
            continue
        # Skip lines that are just numbers, years, dollar signs, percentages
        if re.match(r'^[\s\d,\$%\.\-\/\(\)]+$', line):
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

    # Look for just a year (but not inside UUIDs or hex strings)
    match = re.search(r"(?<![a-fA-F0-9])(20\d{2})(?![a-fA-F0-9])", filename)
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
