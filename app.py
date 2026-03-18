"""
Streamlit app to browse extracted tables and compare extraction methods.

Launch with: streamlit run app.py
"""

import json
from pathlib import Path

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent
INDEX_CSV = PROJECT_ROOT / "data" / "index" / "tables_index.csv"
COMPARISON_JSON = PROJECT_ROOT / "data" / "index" / "comparison_report.json"


def tables_tab():
    """Main tab: browse extracted tables."""
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

    if selected_company != "All":
        filtered = df[df["Company"] == selected_company]
    else:
        filtered = df

    periods = sorted(filtered["Period"].dropna().unique().tolist())
    selected_period = st.sidebar.selectbox("Period", ["All"] + periods)

    if selected_period != "All":
        filtered = filtered[filtered["Period"] == selected_period]

    # Quarter / Annual filter
    if "Report_Type" in filtered.columns:
        report_types = sorted(filtered["Report_Type"].dropna().unique().tolist())
        selected_type = st.sidebar.selectbox("Quarter", ["All"] + report_types)
        if selected_type != "All":
            filtered = filtered[filtered["Report_Type"] == selected_type]

    search = st.sidebar.text_input("Search headings", placeholder="e.g. Balance Sheet")
    if search:
        filtered = filtered[filtered["Heading"].str.contains(search, case=False, na=False)]

    st.markdown(f"**Showing {len(filtered)} of {len(df)} tables**")

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


def comparison_tab():
    """Comparison tab: PDF extraction vs OCR side by side."""
    st.header("PDF Extraction vs OCR Comparison")

    st.markdown("""
**Two methods were used to extract table data:**
- **PDF method** — reads text directly from the PDF file (exact, structured)
- **OCR method** — takes a screenshot of the table, then Tesseract guesses the text (lossy)

The similarity score shows how much of the PDF-extracted text was also found by OCR.
""")

    # Load comparison report
    if not COMPARISON_JSON.exists():
        st.error("No comparison report found. Run `python compare_methods.py` first.")
        return

    with open(COMPARISON_JSON) as f:
        report = json.load(f)

    tables = report.get("tables", [])
    if not tables:
        st.warning("No comparison data available.")
        return

    # Summary metrics
    avg = report.get("average_similarity", 0)
    total = report.get("total_tables", 0)
    perfect = sum(1 for t in tables if t["similarity"] == 100)
    good = sum(1 for t in tables if t["similarity"] > 75)
    low = sum(1 for t in tables if t["similarity"] < 50)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Tables Compared", total)
    col2.metric("Average Similarity", f"{avg}%")
    col3.metric("Good (>75%)", good)
    col4.metric("Low (<50%)", low)

    st.divider()

    # Similarity distribution
    st.subheader("Similarity Distribution")
    sim_df = pd.DataFrame(tables)
    bins = {"0-25%": 0, "25-50%": 0, "50-75%": 0, "75-100%": 0, "100%": 0}
    for s in sim_df["similarity"]:
        if s == 100:
            bins["100%"] += 1
        elif s > 75:
            bins["75-100%"] += 1
        elif s > 50:
            bins["50-75%"] += 1
        elif s > 25:
            bins["25-50%"] += 1
        else:
            bins["0-25%"] += 1

    st.bar_chart(pd.Series(bins))

    st.divider()

    # Filter
    st.subheader("Table Details")
    show_filter = st.selectbox("Show", ["All", "Low similarity (<50%)", "Perfect (100%)"])

    if show_filter == "Low similarity (<50%)":
        tables = [t for t in tables if t["similarity"] < 50]
    elif show_filter == "Perfect (100%)":
        tables = [t for t in tables if t["similarity"] == 100]

    tables = sorted(tables, key=lambda t: t["similarity"])

    for t in tables:
        sim = t["similarity"]
        color = "🔴" if sim < 50 else "🟡" if sim < 75 else "🟢"
        label = f"{color} {sim}% — Page {t['page']}, Table {t['table_index']} — {t['heading'][:60]}"

        with st.expander(label):
            col1, col2, col3 = st.columns(3)
            col1.metric("Similarity", f"{sim}%")
            col2.metric("PDF Lines", t["pdf_lines"])
            col3.metric("OCR Lines", t["ocr_lines"])

            left, right = st.columns(2)
            with left:
                st.markdown("**PDF method (exact):**")
                for line in t.get("pdf_sample", []):
                    st.code(line, language=None)
            with right:
                st.markdown("**OCR method (Tesseract):**")
                for line in t.get("ocr_sample", []):
                    st.code(line, language=None)


def main():
    st.set_page_config(page_title="PDF Table Extractor", layout="wide")
    st.title("PDF Table Extractor")

    tab1, tab2 = st.tabs(["Tables", "Comparison"])

    with tab1:
        tables_tab()

    with tab2:
        comparison_tab()


if __name__ == "__main__":
    main()
