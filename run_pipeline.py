"""
Main entry point: runs table extraction + indexing on all PDFs in data/raw_pdfs/.

Usage:
    python run_pipeline.py                     # uses default data/raw_pdfs/
    python run_pipeline.py /path/to/pdfs       # custom PDF folder
"""

import sys
from pathlib import Path

from src.extract_tables import process_company_folder
from src.build_index import build_index


def main():
    # Determine project root (where this script lives)
    project_root = Path(__file__).resolve().parent

    # Accept optional custom path for raw PDFs
    if len(sys.argv) > 1:
        raw_pdfs_dir = Path(sys.argv[1])
    else:
        raw_pdfs_dir = project_root / "data" / "raw_pdfs"

    if not raw_pdfs_dir.exists():
        print(f"ERROR: PDF directory not found: {raw_pdfs_dir}")
        print("Create it and add company subfolders (e.g., data/raw_pdfs/TSLA/) with PDF files.")
        sys.exit(1)

    # Find all company subfolders
    company_folders = sorted([
        d for d in raw_pdfs_dir.iterdir()
        if d.is_dir() and not d.name.startswith(".")
    ])

    if not company_folders:
        print(f"No company folders found in {raw_pdfs_dir}")
        print("Create subfolders like TSLA/, NVDA/ and add PDFs inside them.")
        sys.exit(1)

    print(f"Found {len(company_folders)} company folder(s): {', '.join(d.name for d in company_folders)}")
    print("=" * 60)

    # Process each company
    all_metadata = []
    total_pdfs = 0

    for folder in company_folders:
        print(f"\n[{folder.name}]")
        pdf_count = len(list(folder.glob("*.pdf")))
        total_pdfs += pdf_count
        metadata = process_company_folder(folder, project_root)
        all_metadata.extend(metadata)

    # Build the master index
    print("\n" + "=" * 60)
    print("Building master index...")
    build_index(all_metadata, project_root)

    # Final summary
    print("\n" + "=" * 60)
    print(f"DONE: Processed {total_pdfs} PDFs, found {len(all_metadata)} tables total.")


if __name__ == "__main__":
    main()
