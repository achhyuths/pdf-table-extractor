"""
OCR extracted table images and save as JSON using Tesseract.

Reads PNG images from data/extracted_tables/, runs OCR, and saves as JSON
with metadata from the CSV index (company, report, period, heading, coordinates).

Usage:
    python ocr_to_json.py                      # all companies
    python ocr_to_json.py --company AAPL       # just Apple
"""

import json
import sys
from pathlib import Path

import pandas as pd
import pytesseract
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent


def load_index():
    """Load the CSV index and build a lookup dict by image filename."""
    csv_path = PROJECT_ROOT / "data" / "index" / "tables_index.csv"
    if not csv_path.exists():
        return {}
    df = pd.read_csv(csv_path, dtype=str)
    lookup = {}
    for _, row in df.iterrows():
        # Image_Path is like "data/extracted_tables/AAPL/AAPL_10K_p04_t01.png"
        img_name = Path(row["Image_Path"]).name
        lookup[img_name] = row.to_dict()
    return lookup


def ocr_image_to_rows(image_path):
    """Run Tesseract OCR on an image and return rows of text."""
    img = Image.open(image_path)
    text = pytesseract.image_to_string(img)
    lines = [line.strip() for line in text.strip().split("\n") if line.strip()]
    return lines


def export_company(company_name, output_base, index_lookup):
    """OCR all images for a company and save as one JSON file."""
    images_dir = PROJECT_ROOT / "data" / "extracted_tables" / company_name
    if not images_dir.exists():
        print(f"  No images found for {company_name}")
        return 0

    images = sorted(images_dir.glob("*.png"))
    if not images:
        print(f"  No PNG files in {images_dir}")
        return 0

    tables = []
    for img_path in images:
        print(f"  {img_path.name}...", end=" ", flush=True)
        try:
            rows = ocr_image_to_rows(img_path)

            # Look up metadata from CSV index
            meta = index_lookup.get(img_path.name, {})

            tables.append({
                "company": meta.get("Company", company_name),
                "report": meta.get("Report", ""),
                "period": meta.get("Period", ""),
                "page": int(meta.get("Page", 0)),
                "table_index": int(meta.get("Table_Index", 0)),
                "heading": meta.get("Heading", ""),
                "image": img_path.name,
                "coordinates": {
                    "x0": float(meta.get("Bbox_X0", 0)),
                    "y0": float(meta.get("Bbox_Y0", 0)),
                    "x1": float(meta.get("Bbox_X1", 0)),
                    "y1": float(meta.get("Bbox_Y1", 0)),
                },
                "rows": len(rows),
                "data": rows,
            })
            print(f"{len(rows)} lines")
        except Exception as e:
            print(f"ERROR: {e}")

    if not tables:
        return 0

    # Save JSON
    output_dir = output_base / company_name
    output_dir.mkdir(parents=True, exist_ok=True)
    out_file = output_dir / f"{company_name}_ocr.json"

    with open(out_file, "w") as f:
        json.dump(tables, f, indent=2)

    print(f"  Saved: {out_file}")
    return len(tables)


def main():
    output_base = PROJECT_ROOT / "data" / "ocr_json"
    index_lookup = load_index()

    if not index_lookup:
        print("WARNING: No CSV index found. Metadata will be empty. Run run_pipeline.py first.")

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

    # Find company folders
    images_root = PROJECT_ROOT / "data" / "extracted_tables"
    if not images_root.exists():
        print(f"ERROR: {images_root} not found. Run run_pipeline.py first.")
        sys.exit(1)

    folders = sorted(d for d in images_root.iterdir() if d.is_dir() and not d.name.startswith("."))

    if company_filter:
        folders = [f for f in folders if f.name == company_filter]
        if not folders:
            print(f"ERROR: company '{company_filter}' not found")
            sys.exit(1)

    total = 0
    for folder in folders:
        print(f"\n[{folder.name}]")
        total += export_company(folder.name, output_base, index_lookup)

    print(f"\nDONE: {total} tables exported to {output_base}")


if __name__ == "__main__":
    main()
