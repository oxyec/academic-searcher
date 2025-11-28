import streamlit as st
import pandas as pd
from src.core import search_all_sources
from src.utils import clean_text

def main():
    st.set_page_config(page_title="Academic Research Assistant", page_icon="📚", layout="wide")

    st.title("📚 Academic Research Assistant")
    st.markdown("""
    This tool automates the process of searching for academic papers.
    It queries **CrossRef**, **Semantic Scholar**, and **Google** (if configured),
    checks for free PDFs via **Unpaywall**, and lets you export the results.
    """)

    # Sidebar settings
    with st.sidebar:
        st.header("Settings")
        limit = st.number_input("Articles per source", min_value=1, max_value=20, value=5)
        st.info("Higher limits make the search take longer.")

    # Main search interface
    query = st.text_input("Enter Research Topic/Keyword", placeholder="e.g. Machine Learning in Healthcare")

    if st.button("Search", type="primary"):
        if not query:
            st.warning("Please enter a search term.")
        else:
            with st.spinner(f"Searching for '{query}'..."):
                results = search_all_sources(query, limit)

            if not results:
                st.error("No results found.")
            else:
                st.success(f"Found {len(results)} articles!")

                # Convert to DataFrame
                df = pd.DataFrame(results)

                # Clean up column names for display
                display_columns = {
                    'source': 'Source',
                    'title': 'Title',
                    'authors': 'Authors',
                    'year': 'Year',
                    'venue': 'Venue',
                    'oa_status': 'OA Status',
                    'pdf_link': 'PDF Link',
                    'doi': 'DOI',
                    'url': 'URL'
                }
                # Select and rename columns if they exist
                cols_to_show = [c for c in display_columns.keys() if c in df.columns]
                df_display = df[cols_to_show].rename(columns=display_columns)

                st.dataframe(df_display, use_container_width=True)

                # CSV Download
                csv = df_display.to_csv(index=False).encode('utf-8-sig')

                st.download_button(
                    label="📥 Download Results as CSV",
                    data=csv,
                    file_name=f"research_results_{query.replace(' ', '_')}.csv",
                    mime="text/csv",
                )

if __name__ == "__main__":
    import sys
    from streamlit.web import cli as stcli

    # Check if running directly via python
    if "streamlit" not in sys.modules:
        sys.argv = ["streamlit", "run", sys.argv[0]]
        sys.exit(stcli.main())
    else:
        main()
