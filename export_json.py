"""
Export table data to JSON (direct from PDF, no OCR).

Reads each PDF with pdfplumber, extracts raw cell data, and saves as JSON
with full metadata (company, report, period, heading, coordinates).

Usage:
    python export_json.py                      # all companies
    python export_json.py --company AAPL       # just Apple
"""

import json
import logging
import re
import sys
import warnings
from pathlib import Path

import pdfplumber

logging.getLogger("pdfminer").setLevel(logging.ERROR)
warnings.filterwarnings("ignore", message=".*Cannot set.*non-stroke color.*")

PROJECT_ROOT = Path(__file__).resolve().parent
MIN_TABLE_HEIGHT = 25


def get_heading(page, bbox):
    """Get heading text above a table."""
    x0, y0, x1, y1 = bbox
    crop_top = max(0, y0 - 150)
    try:
        text = page.within_bbox((0, crop_top, page.width, y0)).extract_text() or ""
    except Exception:
        return ""
    lines = [l.strip() for l in text.strip().split("\n") if l.strip()]
    for line in reversed(lines):
        if len(line) < 15:
            continue
        if re.match(r'^[\d\s,.$%()\-/]+$', line):
            continue
        if line.startswith("("):
            continue
        if re.search(r'\d', line):
            continue
        return line
    return ""


def get_year(filename, plumber_pdf=None):
    """Extract year from filename, or from PDF text if not found."""
    match = re.search(r"(?<![a-fA-F0-9])(20\d{2})(?![a-fA-F0-9])", filename)
    if match:
        return match.group(1)
    if plumber_pdf:
        for page in plumber_pdf.pages[:3]:
            text = page.extract_text() or ""
            match = re.search(r"\b(20\d{2})\b", text)
            if match:
                return match.group(1)
    return ""


def export_pdf(pdf_path, company, output_dir):
    """Extract tables from one PDF and save as JSON with metadata."""
    pdf = pdfplumber.open(pdf_path)
    period = get_year(pdf_path.name, pdf)
    tables_out = []

    try:
        for page_idx, page in enumerate(pdf.pages):
            try:
                tables = page.find_tables()
            except Exception:
                continue
            if not tables:
                continue

            for tbl_idx, table in enumerate(tables):
                x0, y0, x1, y1 = table.bbox
                if (y1 - y0) < MIN_TABLE_HEIGHT:
                    continue

                data = table.extract()
                if not data:
                    continue

                # Clean None to empty string
                cleaned = []
                for row in data:
                    cleaned.append([cell.strip() if cell else "" for cell in row])

                heading = get_heading(page, table.bbox) or f"Table (Page {page_idx + 1}, #{tbl_idx + 1})"

                tables_out.append({
                    "company": company,
                    "report": pdf_path.stem,
                    "period": period,
                    "page": page_idx + 1,
                    "table_index": tbl_idx + 1,
                    "heading": heading,
                    "coordinates": {
                        "x0": round(x0, 1), "y0": round(y0, 1),
                        "x1": round(x1, 1), "y1": round(y1, 1),
                    },
                    "rows": len(cleaned),
                    "columns": len(cleaned[0]) if cleaned else 0,
                    "data": cleaned,
                })
    finally:
        pdf.close()

    if not tables_out:
        return 0

    output_dir.mkdir(parents=True, exist_ok=True)
    out_file = output_dir / f"{pdf_path.stem}.json"
    with open(out_file, "w") as f:
        json.dump(tables_out, f, indent=2)

    return len(tables_out)


def main():
    raw_pdfs = PROJECT_ROOT / "data" / "raw_pdfs"
    output_base = PROJECT_ROOT / "data" / "export_json"

    # Parse args
    company_filter = None
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--company" and i + 1 < len(args):
            company_filter = args[i + 1]
            i += 2
        else:
            i += 1

    if not raw_pdfs.exists():
        print(f"ERROR: {raw_pdfs} not found")
        sys.exit(1)

    folders = sorted(d for d in raw_pdfs.iterdir() if d.is_dir() and not d.name.startswith("."))

    if company_filter:
        folders = [f for f in folders if f.name == company_filter]
        if not folders:
            print(f"ERROR: company '{company_filter}' not found")
            sys.exit(1)

    total = 0
    for folder in folders:
        company = folder.name
        print(f"\n[{company}]")
        for pdf in sorted(folder.glob("*.pdf")):
            print(f"  {pdf.name}...", end=" ", flush=True)
            try:
                count = export_pdf(pdf, company, output_base / company)
                total += count
                print(f"{count} tables")
            except Exception as e:
                print(f"ERROR: {e}")

    print(f"\nDONE: {total} tables exported to {output_base}")


if __name__ == "__main__":
    main()
