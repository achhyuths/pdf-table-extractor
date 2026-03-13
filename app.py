"""
Streamlit viewer app for browsing extracted SEC filing tables.

Launch with:
    streamlit run app.py
"""

from pathlib import Path

import pandas as pd
import streamlit as st

# Project root — resolve relative to this script
PROJECT_ROOT = Path(__file__).resolve().parent
INDEX_CSV = PROJECT_ROOT / "data" / "index" / "tables_index.csv"


def main():
    st.set_page_config(
        page_title="SEC Filing Table Explorer",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.title("SEC Filing Table Explorer")

    # --- Load index ---
    if not INDEX_CSV.exists():
        st.error(
            "No index found. Run the pipeline first:\n\n"
            "```\npython run_pipeline.py\n```"
        )
        return

    df = pd.read_csv(INDEX_CSV)

    if df.empty:
        st.warning("Index is empty — no tables were extracted. Check your PDFs and rerun the pipeline.")
        return

    # --- Sidebar filters ---
    st.sidebar.header("Filters")

    # Company filter
    companies = sorted(df["Company"].unique().tolist())
    company_options = ["All"] + companies
    selected_company = st.sidebar.selectbox("Company", company_options)

    # Filter DataFrame by company first (to populate period dropdown)
    if selected_company != "All":
        company_df = df[df["Company"] == selected_company]
    else:
        company_df = df

    # Period/Report filter
    periods = sorted(company_df["Period"].dropna().unique().tolist())
    period_options = ["All"] + periods
    selected_period = st.sidebar.selectbox("Period / Report", period_options)

    # Heading text search
    search_text = st.sidebar.text_input("Search table headings", placeholder="e.g. Balance Sheet")

    # --- Apply filters ---
    filtered = df.copy()

    if selected_company != "All":
        filtered = filtered[filtered["Company"] == selected_company]

    if selected_period != "All":
        filtered = filtered[filtered["Period"] == selected_period]

    if search_text:
        mask = filtered["Heading"].str.contains(search_text, case=False, na=False)
        filtered = filtered[mask]

    # --- Main area ---
    total = len(df)
    showing = len(filtered)
    st.markdown(f"**Showing {showing} of {total} tables**")

    # Download button
    csv_data = filtered.to_csv(index=False).encode("utf-8")
    st.sidebar.download_button(
        label="Download Filtered Index (CSV)",
        data=csv_data,
        file_name="filtered_tables_index.csv",
        mime="text/csv",
    )

    st.divider()

    # --- Display results ---
    if filtered.empty:
        st.info("No tables match your filters. Try adjusting the filters in the sidebar.")
        return

    for _, row in filtered.iterrows():
        expander_title = f"{row['Company']} | {row['Period']} | {row['Heading']}"

        with st.expander(expander_title):
            col1, col2, col3 = st.columns(3)
            col1.metric("Page", row["Page"])
            col2.metric("Dimensions", f"{row['Rows']} × {row['Columns']}")
            col3.metric("Table #", row["Table_Index"])

            # Display the table image
            img_path = PROJECT_ROOT / row["Image_Path"]
            if img_path.exists():
                st.image(str(img_path), use_container_width=True)
            else:
                st.warning(f"Image not found: {row['Image_Path']}")


if __name__ == "__main__":
    main()
