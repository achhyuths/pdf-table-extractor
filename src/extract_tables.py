"""
Extract tables from SEC PDF filings.

Uses pdfplumber to find tables and PyMuPDF (fitz) to render cropped images.
"""

import logging
import warnings
from pathlib import Path

import fitz  # PyMuPDF
import pdfplumber

from src.utils import (
    build_image_filename,
    ensure_dirs,
    extract_heading_above_table,
    parse_year_from_filename,
)

# Suppress noisy pdfplumber warnings
logging.getLogger("pdfminer").setLevel(logging.ERROR)
warnings.filterwarnings("ignore", message=".*Cannot set.*non-stroke color.*")

# Image rendering DPI
RENDER_DPI = 225

# Padding around the table crop (in PDF points)
PAD_TOP = 150
PAD_BOTTOM = 10
PAD_LEFT = 10
PAD_RIGHT = 10

# Tables shorter than this (in points) are probably false positives
MIN_TABLE_HEIGHT = 25


def has_numbers(table):
    """Check if a table has at least some numeric data."""
    try:
        data = table.extract()
        if not data:
            return False

        number_count = 0
        total_count = 0

        for row in data:
            for cell in row:
                if cell is not None and str(cell).strip():
                    total_count += 1
                    if any(c.isdigit() for c in str(cell)):
                        number_count += 1

        # At least 20% of cells should have numbers
        return total_count > 0 and (number_count / total_count) >= 0.2
    except Exception:
        return False


def extract_tables_from_pdf(pdf_path, company, output_dir):
    """
    Extract all tables from a single PDF file.

    Returns a list of dicts with metadata about each table found.
    """
    report_name = pdf_path.stem
    period = parse_year_from_filename(pdf_path.name)

    tables_metadata = []

    plumber_pdf = pdfplumber.open(pdf_path)
    fitz_doc = fitz.open(pdf_path)

    try:
        for page_idx, plumber_page in enumerate(plumber_pdf.pages):
            page_num = page_idx + 1
            page_width = plumber_page.width
            page_height = plumber_page.height

            # Find tables on this page
            try:
                tables = plumber_page.find_tables()
            except Exception:
                continue

            if not tables:
                continue

            fitz_page = fitz_doc[page_idx]

            for tbl_idx, table in enumerate(tables):
                bbox = table.bbox  # (x0, y0, x1, y1)
                x0, y0, x1, y1 = bbox

                # Skip tiny tables (false positives)
                if (y1 - y0) < MIN_TABLE_HEIGHT:
                    continue

                # Skip tables that don't have numeric data
                if not has_numbers(table):
                    continue

                # Get heading text above the table
                heading = extract_heading_above_table(plumber_page, bbox)
                if not heading:
                    heading = f"Table (Page {page_num}, #{tbl_idx + 1})"

                # Get table dimensions
                raw_data = table.extract()
                num_rows = len(raw_data) if raw_data else 0
                num_cols = len(raw_data[0]) if raw_data and raw_data[0] else 0

                # Crop and save the table as an image
                crop_x0 = max(0, x0 - PAD_LEFT)
                crop_y0 = max(0, y0 - PAD_TOP)
                crop_x1 = min(page_width, x1 + PAD_RIGHT)
                crop_y1 = min(page_height, y1 + PAD_BOTTOM)

                clip = fitz.Rect(crop_x0, crop_y0, crop_x1, crop_y1)
                zoom = RENDER_DPI / 72
                mat = fitz.Matrix(zoom, zoom)
                pix = fitz_page.get_pixmap(matrix=mat, clip=clip)

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
                })

    finally:
        plumber_pdf.close()
        fitz_doc.close()

    return tables_metadata


def process_company_folder(company_folder, project_root):
    """
    Process all PDFs in a company folder.
    Returns combined list of table metadata for all PDFs.
    """
    company = company_folder.name
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
