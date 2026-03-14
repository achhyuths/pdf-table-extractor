"""
Main script: extracts tables from all PDFs in data/raw_pdfs/ and builds an index.

Usage:
    python run_pipeline.py
    python run_pipeline.py /path/to/pdfs
"""

import sys
from pathlib import Path

from src.extract_tables import process_company_folder
from src.build_index import build_index


def main():
    project_root = Path(__file__).resolve().parent

    # Get PDF directory from command line or use default
    if len(sys.argv) > 1:
        raw_pdfs_dir = Path(sys.argv[1])
    else:
        raw_pdfs_dir = project_root / "data" / "raw_pdfs"

    if not raw_pdfs_dir.exists():
        print(f"ERROR: PDF directory not found: {raw_pdfs_dir}")
        sys.exit(1)

    # Find company subfolders (e.g. TSLA/, NVDA/)
    company_folders = sorted([
        d for d in raw_pdfs_dir.iterdir()
        if d.is_dir() and not d.name.startswith(".")
    ])

    if not company_folders:
        print(f"No company folders found in {raw_pdfs_dir}")
        sys.exit(1)

    print(f"Found {len(company_folders)} company folder(s)")
    print("=" * 50)

    # Extract tables from each company's PDFs
    all_metadata = []
    for folder in company_folders:
        print(f"\n[{folder.name}]")
        metadata = process_company_folder(folder, project_root)
        all_metadata.extend(metadata)

    # Build the index CSV
    print("\n" + "=" * 50)
    print("Building index...")
    build_index(all_metadata, project_root)

    print(f"\nDONE: Found {len(all_metadata)} tables total.")


if __name__ == "__main__":
    main()
