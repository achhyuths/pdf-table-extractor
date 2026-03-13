"""
Build a master index (CSV + Excel) cataloging every extracted table.
"""

from pathlib import Path
from collections import Counter

import pandas as pd
from openpyxl.styles import Font


# Column order for the output index
INDEX_COLUMNS = [
    "Company",
    "Report",
    "Period",
    "Page",
    "Table_Index",
    "Heading",
    "Image_Path",
    "Rows",
    "Columns",
]


def build_index(tables_metadata: list[dict], project_root: Path) -> pd.DataFrame:
    """
    Build a master index DataFrame from table metadata and save to CSV + Excel.

    Args:
        tables_metadata: list of metadata dicts from extraction
        project_root: root of the project (for output paths)

    Returns:
        The index DataFrame.
    """
    if not tables_metadata:
        print("No tables to index.")
        return pd.DataFrame(columns=INDEX_COLUMNS)

    # Map raw metadata keys to clean column names
    records = []
    for m in tables_metadata:
        records.append({
            "Company": m["company"],
            "Report": m["report_name"],
            "Period": m["period"],
            "Page": m["page_number"],
            "Table_Index": m["table_index"],
            "Heading": m["heading"],
            "Image_Path": m["image_path"],
            "Rows": m["num_rows"],
            "Columns": m["num_cols"],
        })

    df = pd.DataFrame(records, columns=INDEX_COLUMNS)

    # Sort by Company, Period, Page, Table_Index
    df = df.sort_values(["Company", "Period", "Page", "Table_Index"]).reset_index(drop=True)

    # Ensure output directory exists
    index_dir = project_root / "data" / "index"
    index_dir.mkdir(parents=True, exist_ok=True)

    # Save CSV
    csv_path = index_dir / "tables_index.csv"
    df.to_csv(csv_path, index=False)
    print(f"  Saved CSV index: {csv_path}")

    # Save Excel with formatting
    xlsx_path = index_dir / "tables_index.xlsx"
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Tables")
        ws = writer.sheets["Tables"]

        # Bold header row
        bold_font = Font(bold=True)
        for cell in ws[1]:
            cell.font = bold_font

        # Auto-filter on all columns
        ws.auto_filter.ref = ws.dimensions

        # Adjust column widths for readability
        for col_cells in ws.columns:
            max_len = max(len(str(cell.value or "")) for cell in col_cells)
            col_letter = col_cells[0].column_letter
            ws.column_dimensions[col_letter].width = min(max_len + 4, 60)

    print(f"  Saved Excel index: {xlsx_path}")

    # Print summary
    _print_summary(df)

    return df


def _print_summary(df: pd.DataFrame) -> None:
    """Print a summary of the index."""
    print("\n--- Index Summary ---")

    # Tables per company
    company_counts = df["Company"].value_counts()
    for company, count in company_counts.items():
        print(f"  {company}: {count} tables")

    # Most common headings (top 10)
    heading_counts = Counter(df["Heading"].tolist())
    print("\n  Most common table headings:")
    for heading, count in heading_counts.most_common(10):
        # Truncate long headings for display
        display = heading[:70] + "..." if len(heading) > 70 else heading
        print(f"    [{count}x] {display}")
