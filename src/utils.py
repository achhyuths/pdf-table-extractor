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
        # Skip data rows (lines with comma-formatted numbers like 8,006 or $178,353)
        if re.search(r'\d{1,3}(,\d{3})', line):
            continue
        # This looks like a real heading
        return line

    return ""


def parse_year_from_filename(filename):
    """
    Try to get the year from a PDF filename.

    Examples:
        'TSLA-Q3-2025-Update.pdf' -> '2025'
        '10K-Q4-2025-as-filed.pdf' -> '2025'
        '9a129eb1-5997-470d-b0cb-ac02db203108.pdf' -> ''  (UUID, no year)
    """
    # Look for a year that's not buried inside a UUID/hex string
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
