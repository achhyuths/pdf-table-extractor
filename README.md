# SEC Filing Table Extractor

Extracts tables from SEC quarterly/annual report PDFs (10-Q, 10-K, earnings updates), saves cropped high-resolution images of each table, builds a searchable master index, and provides a Streamlit app for browsing. Pure Python — no LLMs or AI APIs.

## Setup

```bash
pip install -r requirements.txt
```

## Project Structure

```
data/
├── raw_pdfs/           # Put your PDFs here, organized by company
│   ├── TSLA/
│   │   ├── TSLA-Q1-2025-Update.pdf
│   │   └── TSLA-Q2-2025-Update.pdf
│   └── NVDA/
│       └── ...
├── extracted_tables/   # Output: cropped table images (auto-generated)
└── index/              # Output: master index CSV + Excel (auto-generated)
```

## Adding PDFs

1. Create a subfolder under `data/raw_pdfs/` named with the company ticker (e.g., `TSLA`, `NVDA`)
2. Place the PDF files inside that folder
3. Run the pipeline

## Running the Pipeline

```bash
python run_pipeline.py
```

This will:
- Scan all company folders under `data/raw_pdfs/`
- Detect and extract every table from each PDF
- Save cropped PNG images of each table
- Build a master index (CSV + Excel) in `data/index/`

You can also pass a custom PDF directory:
```bash
python run_pipeline.py /path/to/my/pdfs
```

## Launching the Viewer App

```bash
streamlit run app.py
```

The app lets you:
- Filter tables by company, period, and heading text
- View high-resolution images of each table
- Download the filtered index as CSV

## Example Output

After running the pipeline on Tesla earnings PDFs:

```
Found 1 company folder(s): TSLA
============================================================

[TSLA]
  Processing TSLA/TSLA-Q3-2025-Update.pdf... Found 12 tables

============================================================
Building master index...
  Saved CSV index: data/index/tables_index.csv
  Saved Excel index: data/index/tables_index.xlsx

--- Index Summary ---
  TSLA: 12 tables

============================================================
DONE: Processed 1 PDFs, found 12 tables total.
```

## Libraries Used

- **pdfplumber** — table detection and text extraction
- **PyMuPDF (fitz)** — high-quality image rendering of table regions
- **pandas** — index building and data manipulation
- **openpyxl** — Excel export with formatting
- **Pillow** — image processing
- **streamlit** — interactive viewer app
