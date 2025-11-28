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
# Try import AgGrid
try:
    from st_aggrid import AgGrid, GridOptionsBuilder, JsCode, GridUpdateMode
    AGGRID_AVAILABLE = True
except Exception:
    AGGRID_AVAILABLE = False

st.set_page_config(page_title="Academic Research Assistant — Full Suite", page_icon="📚", layout="wide")

# ----------------------
# Helpers
# ----------------------
def make_link_renderer(field):
    # JS renderer that creates a small link icon + short text
    return JsCode(f"""
    function(params) {{
        if (!params.value) return '';
        var url = params.value;
        var short = url.length > 60 ? url.substring(0,57) + '...' : url;
        return `<a href="${{url}}" target="_blank" rel="noopener noreferrer" style="color: inherit; text-decoration: underline;">${{short}}</a>`;
    }}
    """)

def make_button_renderer(url_field, label="Open"):
    # JS renderer that creates a button opening the URL in a new tab
    return JsCode(f"""
    function(params) {{
        var url = params.data['{url_field}'];
        if (!url) return '';
        return `<button onclick="window.open('${{url}}', '_blank')">{label}</button>`;
    }}
    """)

def to_bibtex_entry(row):
    # Simple bibtex generator (article/book fallback)
    title = row.get('Title', 'No title').replace('\n',' ')
    year = row.get('Year', 'n.d.')
    authors = row.get('Authors', '')
    doi = row.get('DOI', '')
    citekey = f"{clean_text(str(authors).split(',')[0])[:20]}_{year}"
    bib = f"@article{{{citekey},\n  title = {{{title}}},\n"
    if authors:
        bib += f"  author = {{{authors}}},\n"
    bib += f"  year = {{{year}}},\n"
    if doi:
        bib += f"  doi = {{{doi}}},\n"
    bib += "}\n"
    return bib

def to_ris_entry(row):
    # Very small RIS generator for Zotero/EndNote import
    title = row.get('Title', 'No title')
    year = row.get('Year', '')
    authors = row.get('Authors', '')
    doi = row.get('DOI', '')
    url = row.get('URL', '')
    ris = "TY  - JOUR\n"
    if authors:
        for a in (authors.split(',') if isinstance(authors, str) else []):
            if a.strip():
                ris += f"AU  - {a.strip()}\n"
    ris += f"TI  - {title}\n"
    if year:
        ris += f"PY  - {year}\n"
    if doi:
        ris += f"DO  - {doi}\n"
    if url:
        ris += f"UR  - {url}\n"
    ris += "ER  - \n\n"
    return ris

def aggrid_show(df):
    """Show dataframe with AgGrid and return selected rows (list of dicts)."""
    if not AGGRID_AVAILABLE:
        st.dataframe(df, use_container_width=True)
        return []

    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_default_column(filter=True, sortable=True, resizable=True)
    gb.configure_selection(selection_mode="single", use_checkbox=False)
    gb.configure_pagination(paginationAutoPageSize=False, paginationPageSize=10)

    # If PDF/URL columns exist, add renderers
    if 'PDF' in df.columns:
        gb.configure_column('PDF', header_name='PDF', cellRenderer=JsCode("""
            function(params) {
                if(!params.value) return '';
                const url = params.value;
                return `<button onclick="window.open('${url}', '_blank')">Open PDF</button>`;
            }
        """))
    if 'DOI' in df.columns:
        gb.configure_column('DOI', header_name='DOI', cellRenderer=JsCode("""
            function(params) {
                if(!params.value) return '';
                const doi = params.value;
                const url = doi.startsWith('http') ? doi : 'https://doi.org/' + doi;
                return `<a href="${url}" target="_blank" rel="noopener noreferrer">${doi}</a>`;
            }
        """))
    if 'URL' in df.columns:
        gb.configure_column('URL', header_name='URL', cellRenderer=JsCode("""
            function(params) {
                if(!params.value) return '';
                const url = params.value;
                const short = url.length>60 ? url.substring(0,57) + '...' : url;
                return `<a href="${url}" target="_blank" rel="noopener noreferrer">${short}</a>`;
            }
        """))

    grid_options = gb.build()
    grid_response = AgGrid(
        df,
        gridOptions=grid_options,
        enable_enterprise_modules=False,
        fit_columns_on_grid_load=True,
        update_mode=GridUpdateMode.SELECTION_CHANGED,
        allow_unsafe_jscode=True,
    )
    selected = grid_response.get('selected_rows', [])
    return selected

# ----------------------
# Layout
# ----------------------
st.title("📚 Academic Research Assistant — Everything Pack")
st.markdown("Search CrossRef, Semantic Scholar, Google (opt), check OA via Unpaywall, preview PDFs, export BibTeX/RIS, and more.")

# Sidebar
with st.sidebar:
    st.subheader("Settings")
    limit = st.number_input("Articles per source", min_value=1, max_value=100, value=5, key="limit_input")
    sources = st.multiselect("Sources", options=['CrossRef','Semantic Scholar','Google'], default=['CrossRef','Semantic Scholar'], key='sources_select')
    year_min, year_max = st.slider("Year range", 1900, 2026, (2000, 2025), key='year_slider')
    oa_filter = st.selectbox("Open access", options=['Any','Only OA','Only Closed'], index=0, key='oa_select')
    st.markdown("---")
    st.markdown("**Export / Tools**")
    st.checkbox("Show PDF preview panel", value=True, key='pdf_preview_checkbox')
    st.caption("Tip: increase limits for broader results. Higher = slower.")

# Search area
col1, col2 = st.columns([8,2])
with col1:
    query = st.text_input("🔍 Search papers", placeholder="e.g. Machine Learning in Healthcare", key='query_input')
with col2:
    search_btn = st.button("Search", type='primary', key='search_btn')

# Determine run
if 'last_query' not in st.session_state:
    st.session_state['last_query'] = ''
run_search = False
if search_btn:
    run_search = True
elif query and query.strip() and query.strip() != st.session_state['last_query']:
    # Enter pressed / new input
    run_search = True

selected_rows = []
df_display = pd.DataFrame()

if run_search:
    st.session_state['last_query'] = query.strip()
    q = query.strip()
    if not q:
        st.warning("Lütfen bir arama terimi girin.")
    else:
        with st.spinner(f"Searching '{q}'..."):
            # Expect search_all_sources to accept sources list and limit
            results = search_all_sources(q, limit=limit, sources=sources)
        if not results:
            st.error("No results found.")
        else:
            st.success(f"Found {len(results)} raw results.")
            df = pd.DataFrame(results)

            # Map and rename
            column_map = {
                'source':'Source','title':'Title','authors':'Authors','year':'Year',
                'venue':'Venue','oa_status':'OA','pdf_link':'PDF','doi':'DOI','url':'URL'
            }
            cols = [c for c in column_map.keys() if c in df.columns]
            df_display = df[cols].rename(columns=column_map)

            # Normalize authors to string
            if 'Authors' in df_display.columns:
                df_display['Authors'] = df_display['Authors'].apply(lambda x: ', '.join(x) if isinstance(x,(list,tuple)) else x)

            # Apply filters
            if 'Year' in df_display.columns:
                df_display = df_display[(df_display['Year'] >= year_min) & (df_display['Year'] <= year_max)]
            if oa_filter != 'Any' and 'OA' in df_display.columns:
                want_oa = (oa_filter == 'Only OA')
                df_display = df_display[df_display['OA'].apply(lambda v: bool(v) if pd.notna(v) else False) == want_oa]
            if 'Source' in df_display.columns and sources:
                df_display = df_display[df_display['Source'].isin(sources)]

            st.markdown(f"**Displayed results:** {len(df_display)}")

            # Layout: table + right panel for details/preview
            if st.session_state.get('pdf_preview_checkbox', True):
                left, right = st.columns([3,2])
            else:
                left = st.container()
                right = None

            with left:
                if AGGRID_AVAILABLE:
                    selected_rows = aggrid_show(df_display)
                else:
                    st.dataframe(df_display, use_container_width=True)

                # Download CSV
                csv = df_display.to_csv(index=False).encode('utf-8-sig')
                st.download_button("📥 Download CSV", csv, file_name=f"results_{q.replace(' ','_')}.csv", mime='text/csv', key='dl_csv')

                # BibTeX & RIS exports for all displayed rows
                if st.button("📚 Generate BibTeX for displayed", key='gen_bib_all'):
                    bibs = [to_bibtex_entry(row) for _, row in df_display.iterrows()]
                    bibtxt = "\n".join(bibs)
                    st.download_button("Download BibTeX", data=bibtxt.encode('utf-8'), file_name=f"citations_{q.replace(' ','_')}.bib", mime='text/plain', key='dl_bib_all')

                if st.button("🔁 Export RIS for Zotero/EndNote", key='gen_ris_all'):
                    ris_txt = "".join([to_ris_entry(row) for _, row in df_display.iterrows()])
                    st.download_button("Download RIS", data=ris_txt.encode('utf-8'), file_name=f"citations_{q.replace(' ','_')}.ris", mime='text/plain', key='dl_ris_all')

            # Right panel: details
            if right is not None:
                with right:
                    st.subheader("Selected item")
                    if selected_rows:
                        sel = selected_rows[0]
                        # Show fields
                        st.markdown(f"**Title:** {sel.get('Title','-')}")
                        st.markdown(f"**Authors:** {sel.get('Authors','-')}")
                        st.markdown(f"**Year / Venue:** {sel.get('Year','-')} / {sel.get('Venue','-')}")
                        st.markdown(f"**DOI:** {sel.get('DOI','-')}")
                        st.markdown(f"**Source:** {sel.get('Source','-')}")
                        st.markdown("---")
                        # BibTeX for selected
                        bib = to_bibtex_entry(sel)
                        st.text_area("BibTeX (copy)", value=bib, height=160, key='bibtex_area')
                        if st.download_button("Download selected BibTeX", data=bib.encode('utf-8'), file_name=f"cite_selected_{q.replace(' ','_')}.bib", mime='text/plain', key='dl_bib_sel'):
                            pass
                        # RIS for selected
                        ris = to_ris_entry(sel)
                        if st.download_button("Download selected RIS (Zotero)", data=ris.encode('utf-8'), file_name=f"cite_selected_{q.replace(' ','_')}.ris", mime='text/plain', key='dl_ris_sel'):
                            pass

                        # PDF preview if exists
                        pdf_url = sel.get('PDF') or sel.get('pdf_link') or None
                        if pdf_url:
                            st.markdown("**PDF Preview:**")
                            # iframe preview (may be blocked by CORS)
                            try:
                                st.components.v1.iframe(pdf_url, height=500, scrolling=True)
                            except Exception as e:
                                st.write("Preview not available — opening in new tab:")
                                st.write(f"[Open PDF]({pdf_url})")
                        else:
                            st.info("No PDF link available for this item.")
                    else:
                        st.write("Select a row in the table to see details and preview.")

# Footer notes
st.markdown("---")
st.caption("Pro tip: AgGrid provides best UX (pip install streamlit-aggrid). PDF inline preview may be blocked by some servers (CORS) — use 'Open PDF' button in that case.")
st.caption("Developed by Oxyec. Powered by Streamlit.")
