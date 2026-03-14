"""
Build a CSV index of all extracted tables.
"""

import pandas as pd


COLUMNS = [
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


def build_index(tables_metadata, project_root):
    """
    Build a CSV index from table metadata and save it.
    Returns the DataFrame.
    """
    if not tables_metadata:
        print("No tables to index.")
        return pd.DataFrame(columns=COLUMNS)

    # Convert metadata dicts to clean column names
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

    df = pd.DataFrame(records, columns=COLUMNS)
    df = df.sort_values(["Company", "Period", "Page", "Table_Index"]).reset_index(drop=True)

    # Save CSV
    index_dir = project_root / "data" / "index"
    index_dir.mkdir(parents=True, exist_ok=True)

    csv_path = index_dir / "tables_index.csv"
    df.to_csv(csv_path, index=False)
    print(f"  Saved index: {csv_path}")

    # Print table counts per company
    for company, count in df["Company"].value_counts().items():
        print(f"  {company}: {count} tables")

    return df
