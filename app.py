"""
Streamlit app to browse extracted tables.

Launch with: streamlit run app.py
"""

from pathlib import Path

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent
INDEX_CSV = PROJECT_ROOT / "data" / "index" / "tables_index.csv"


def main():
    st.set_page_config(page_title="PDF Table Extractor", layout="wide")
    st.title("PDF Table Extractor")

    # Load index
    if not INDEX_CSV.exists():
        st.error("No index found. Run `python run_pipeline.py` first.")
        return

    df = pd.read_csv(INDEX_CSV, dtype={"Period": str})
    if df.empty:
        st.warning("Index is empty. Check your PDFs and rerun the pipeline.")
        return

    # Sidebar filters
    st.sidebar.header("Filters")

    companies = sorted(df["Company"].unique().tolist())
    selected_company = st.sidebar.selectbox("Company", ["All"] + companies)

    # Filter by company first so period dropdown only shows relevant periods
    if selected_company != "All":
        filtered = df[df["Company"] == selected_company]
    else:
        filtered = df

    periods = sorted(filtered["Period"].dropna().unique().tolist())
    selected_period = st.sidebar.selectbox("Period", ["All"] + periods)

    if selected_period != "All":
        filtered = filtered[filtered["Period"] == selected_period]

    # Text search
    search = st.sidebar.text_input("Search headings", placeholder="e.g. Balance Sheet")
    if search:
        filtered = filtered[filtered["Heading"].str.contains(search, case=False, na=False)]

    st.markdown(f"**Showing {len(filtered)} of {len(df)} tables**")

    # Download button
    st.sidebar.download_button(
        label="Download CSV",
        data=filtered.to_csv(index=False).encode("utf-8"),
        file_name="filtered_tables.csv",
        mime="text/csv",
    )

    st.divider()

    if filtered.empty:
        st.info("No tables match your filters.")
        return

    # Show each table
    for _, row in filtered.iterrows():
        report_type = row.get("Report_Type", "")
        label = f"{row['Company']} | {row['Period']} {report_type} | {row['Heading']}"

        with st.expander(label):
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Page", row["Page"])
            col2.metric("Size", f"{row['Rows']} x {row['Columns']}")
            col3.metric("Table #", row["Table_Index"])
            col4.metric("Type", report_type if report_type else "—")

            img_path = PROJECT_ROOT / row["Image_Path"]
            if img_path.exists():
                st.image(str(img_path), use_container_width=True)
            else:
                st.warning(f"Image not found: {row['Image_Path']}")


if __name__ == "__main__":
    main()
