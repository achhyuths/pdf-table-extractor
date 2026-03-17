"""
OCR extracted table images and save as Markdown using Tesseract.

Reads PNG images from data/extracted_tables/, runs OCR, and saves as .md files
with metadata from the CSV index (company, report, period, heading, coordinates).

Usage:
    python ocr_to_markdown.py                      # all companies
    python ocr_to_markdown.py --company AAPL       # just Apple
"""

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
        img_name = Path(row["Image_Path"]).name
        lookup[img_name] = row.to_dict()
    return lookup


def ocr_image_to_rows(image_path):
    """Run Tesseract OCR on an image and return rows of text."""
    img = Image.open(image_path)
    text = pytesseract.image_to_string(img)
    lines = [line.strip() for line in text.strip().split("\n") if line.strip()]
    return lines


def rows_to_markdown(rows):
    """Convert OCR text rows into a markdown table."""
    if not rows:
        return ""

    # Split each row by multiple spaces (common OCR column separator)
    split_rows = []
    for row in rows:
        cols = [c.strip() for c in row.split("  ") if c.strip()]
        split_rows.append(cols)

    max_cols = max(len(r) for r in split_rows)

    lines = []
    for i, row in enumerate(split_rows):
        padded = row + [""] * (max_cols - len(row))
        lines.append("| " + " | ".join(padded) + " |")
        if i == 0:
            lines.append("| " + " | ".join(["---"] * max_cols) + " |")

    return "\n".join(lines)


def export_company(company_name, output_base, index_lookup):
    """OCR all images for a company and save as one Markdown file."""
    images_dir = PROJECT_ROOT / "data" / "extracted_tables" / company_name
    if not images_dir.exists():
        print(f"  No images found for {company_name}")
        return 0

    images = sorted(images_dir.glob("*.png"))
    if not images:
        print(f"  No PNG files in {images_dir}")
        return 0

    sections = []
    count = 0
    for img_path in images:
        print(f"  {img_path.name}...", end=" ", flush=True)
        try:
            rows = ocr_image_to_rows(img_path)
            md_table = rows_to_markdown(rows)

            # Look up metadata from CSV index
            meta = index_lookup.get(img_path.name, {})
            heading = meta.get("Heading", img_path.stem)
            report = meta.get("Report", "")
            period = meta.get("Period", "")
            page = meta.get("Page", "")
            tbl_idx = meta.get("Table_Index", "")
            x0 = meta.get("Bbox_X0", "")
            y0 = meta.get("Bbox_Y0", "")
            x1 = meta.get("Bbox_X1", "")
            y1 = meta.get("Bbox_Y1", "")

            # Build section with metadata
            section = f"## {heading}\n"
            section += f"**Company:** {company_name} | **Report:** {report} | **Period:** {period}\n"
            section += f"**Page:** {page} | **Table:** {tbl_idx}\n"
            section += f"**Coordinates:** ({x0}, {y0}, {x1}, {y1})\n"
            section += f"**Image:** {img_path.name}\n"
            section += f"\n{md_table}"

            sections.append(section)
            count += 1
            print(f"{len(rows)} lines")
        except Exception as e:
            print(f"ERROR: {e}")

    if not sections:
        return 0

    # Save Markdown
    output_dir = output_base / company_name
    output_dir.mkdir(parents=True, exist_ok=True)
    out_file = output_dir / f"{company_name}_ocr.md"

    with open(out_file, "w") as f:
        f.write(f"# {company_name} — OCR Tables\n\n")
        f.write("\n\n---\n\n".join(sections) + "\n")

    print(f"  Saved: {out_file}")
    return count


def main():
    output_base = PROJECT_ROOT / "data" / "ocr_markdown"
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
