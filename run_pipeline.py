"""
Extract tables from PDF filings and build a CSV index.

Usage: python run_pipeline.py
"""

import logging
import re
import sys
import warnings
from pathlib import Path

import fitz  # PyMuPDF
import pandas as pd
import pdfplumber

# Suppress noisy warnings
logging.getLogger("pdfminer").setLevel(logging.ERROR)
warnings.filterwarnings("ignore", message=".*Cannot set.*non-stroke color.*")

PROJECT_ROOT = Path(__file__).resolve().parent
RENDER_DPI = 225
PAD_TOP = 150
PAD_BOTTOM = 10
PAD_LEFT = 10
PAD_RIGHT = 10
MIN_TABLE_HEIGHT = 25


def get_heading(page, bbox):
    """Get the heading above a table by finding the closest title-like line."""
    x0, y0, x1, y1 = bbox
    crop_top = max(0, y0 - 150)
    try:
        text = page.within_bbox((0, crop_top, page.width, y0)).extract_text() or ""
    except Exception:
        return ""
    lines = [l.strip() for l in text.strip().split("\n") if l.strip()]
    # Walk from bottom to top, looking for a real title
    for line in reversed(lines):
        if len(line) < 10:
            continue
        if any(c.isdigit() for c in line):
            continue
        # Skip parenthetical notes like "(Unaudited)" or "(In millions...)"
        if line.startswith("("):
            continue
        return line
    return ""


def has_numbers(table):
    """Check if a table has at least 20% numeric cells."""
    try:
        data = table.extract()
        if not data:
            return False
        nums = 0
        total = 0
        for row in data:
            for cell in row:
                if cell and str(cell).strip():
                    total += 1
                    if any(c.isdigit() for c in str(cell)):
                        nums += 1
        return total > 0 and (nums / total) >= 0.2
    except Exception:
        return False


def get_year(filename, plumber_pdf=None):
    """Extract year from filename. If not found, look inside the PDF text."""
    match = re.search(r"(?<![a-fA-F0-9])(20\d{2})(?![a-fA-F0-9])", filename)
    if match:
        return match.group(1)
    # Filename has no year (e.g. UUID), so check first 3 pages of the PDF
    if plumber_pdf:
        for page in plumber_pdf.pages[:3]:
            text = page.extract_text() or ""
            match = re.search(r"\b(20\d{2})\b", text)
            if match:
                return match.group(1)
    return ""


def extract_tables(pdf_path, company, output_dir):
    """Extract all tables from a PDF. Returns list of metadata dicts."""
    report = pdf_path.stem
    results = []

    plumber_pdf = pdfplumber.open(pdf_path)
    fitz_doc = fitz.open(pdf_path)
    period = get_year(pdf_path.name, plumber_pdf)

    try:
        for page_idx, page in enumerate(plumber_pdf.pages):
            page_num = page_idx + 1

            try:
                tables = page.find_tables()
            except Exception:
                continue

            if not tables:
                continue

            fitz_page = fitz_doc[page_idx]

            for tbl_idx, table in enumerate(tables):
                x0, y0, x1, y1 = table.bbox

                if (y1 - y0) < MIN_TABLE_HEIGHT:
                    continue
                if not has_numbers(table):
                    continue

                heading = get_heading(page, table.bbox) or f"Table (Page {page_num}, #{tbl_idx + 1})"

                data = table.extract()
                rows = len(data) if data else 0
                cols = len(data[0]) if data and data[0] else 0

                # Save cropped image
                clip = fitz.Rect(
                    max(0, x0 - PAD_LEFT), max(0, y0 - PAD_TOP),
                    min(page.width, x1 + PAD_RIGHT), min(page.height, y1 + PAD_BOTTOM),
                )
                zoom = RENDER_DPI / 72
                pix = fitz_page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=clip)

                img_name = f"{company}_{report}_p{page_num:02d}_t{tbl_idx + 1:02d}.png"
                pix.save(str(output_dir / img_name))

                results.append({
                    "Company": company, "Report": report, "Period": period,
                    "Page": page_num, "Table_Index": tbl_idx + 1, "Heading": heading,
                    "Image_Path": f"data/extracted_tables/{company}/{img_name}",
                    "Rows": rows, "Columns": cols,
                })

    finally:
        plumber_pdf.close()
        fitz_doc.close()

    return results


def main():
    raw_pdfs = Path(sys.argv[1]) if len(sys.argv) > 1 else PROJECT_ROOT / "data" / "raw_pdfs"

    if not raw_pdfs.exists():
        print(f"ERROR: {raw_pdfs} not found")
        sys.exit(1)

    folders = sorted(d for d in raw_pdfs.iterdir() if d.is_dir() and not d.name.startswith("."))
    if not folders:
        print(f"No company folders in {raw_pdfs}")
        sys.exit(1)

    print(f"Found {len(folders)} company folder(s)\n" + "=" * 50)

    all_tables = []
    for folder in folders:
        company = folder.name
        output_dir = PROJECT_ROOT / "data" / "extracted_tables" / company
        output_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n[{company}]")
        for pdf in sorted(folder.glob("*.pdf")):
            print(f"  {pdf.name}...", end=" ", flush=True)
            try:
                tables = extract_tables(pdf, company, output_dir)
                all_tables.extend(tables)
                print(f"{len(tables)} tables")
            except Exception as e:
                print(f"ERROR: {e}")

    # Save CSV index
    if all_tables:
        df = pd.DataFrame(all_tables)
        df = df.sort_values(["Company", "Period", "Page", "Table_Index"]).reset_index(drop=True)
        csv_dir = PROJECT_ROOT / "data" / "index"
        csv_dir.mkdir(parents=True, exist_ok=True)
        df.to_csv(csv_dir / "tables_index.csv", index=False)

    print(f"\nDONE: {len(all_tables)} tables total")


if __name__ == "__main__":
    main()
