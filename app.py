import sys
import streamlit as st
import pandas as pd
import altair as alt
from src.core import search_all_sources
from src.utils import clean_text
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ----------------------
# 1. Page Config
# ----------------------
st.set_page_config(page_title="Academic Research Assistant — Pro", page_icon="🎓", layout="wide")

# ----------------------
# 2. Imports & Helpers
# ----------------------

def to_bibtex_entry(row):
    # Simple bibtex generator
    title = str(row.get('Title', 'No title')).replace('\n',' ')
    year = str(row.get('Year', 'n.d.'))
    authors = str(row.get('Authors', ''))
    doi = str(row.get('DOI', ''))
    
    first_author = authors.split(',')[0] if authors else "Unknown"
    citekey = f"{clean_text(first_author)[:20]}_{year}"
    
    bib = f"@article{{{citekey},\n  title = {{{title}}},\n"
    if authors:
        bib += f"  author = {{{authors}}},\n"
    bib += f"  year = {{{year}}},\n"
    if doi:
        bib += f"  doi = {{{doi}}},\n"
    bib += "}\n"
    return bib

# ----------------------
# 3. Main Application Logic
# ----------------------
def main():
    st.title("🎓 Academic Research Assistant — Pro Edition")
    st.markdown("Advanced paper discovery with citation metrics, visual analytics, and full-text access checks.")

    # --- Sidebar ---
    with st.sidebar:
        st.header("⚙️ Control Panel")
        
        st.subheader("Search Parameters")
        query = st.text_input("Research Topic", placeholder="e.g. Deep Learning in Healthcare", key='query_input')
        search_btn = st.button("🚀 Start Research", type='primary', use_container_width=True)
        
        st.markdown("---")
        limit = st.slider("Results per source", 1, 50, 10, help="More results = Slower search")
        
        # Updated Source Selection with FREE options
        sources = st.multiselect("Data Sources", options=['OpenAlex', 'ArXiv', 'CrossRef'], default=['OpenAlex', 'ArXiv'])
        
        year_min, year_max = st.slider("Publication Year", 1980, 2026, (2015, 2025))
        
        st.markdown("---")
        st.subheader("Filters")
        oa_filter = st.selectbox("Access Type", options=['All Papers','Open Access Only'], index=0)
        min_citations = st.number_input("Min. Citations", 0, 10000, 0, step=10)

    # --- State Management ---
    if 'search_results' not in st.session_state:
        st.session_state['search_results'] = []
    if 'last_query' not in st.session_state:
        st.session_state['last_query'] = ''
    
    # Logic to trigger search
    run_search = False
    if search_btn:
        run_search = True
    elif query and query.strip() and query.strip() != st.session_state['last_query']:
        run_search = True

    # --- Execution Phase ---
    if run_search:
        st.session_state['last_query'] = query.strip()
        q = query.strip()
        
        if not q:
            st.toast("⚠️ Please enter a search term.")
        else:
            with st.spinner(f"🔍 Analyzing academic databases for '{q}'..."):
                try:
                    # Search
                    results = search_all_sources(q, limit=limit, sources=sources)
                    st.session_state['search_results'] = results
                except Exception as e:
                    st.error(f"An error occurred: {e}")

    # --- Display Phase ---
    if st.session_state['search_results']:
        results = st.session_state['search_results']
        
        if not results:
            st.warning("No results found. Try broadening your keywords.")
        else:
            df = pd.DataFrame(results)

            # 1. Renaming & Normalization
            column_map = {
                'source':'Source', 'title':'Title', 'authors':'Authors', 'year':'Year',
                'venue':'Venue', 'oa_status':'OA', 'pdf_link':'PDF', 'doi':'DOI', 
                'url':'URL', 'citations': 'Cites', 'abstract': 'Abstract'
            }
            cols = [c for c in column_map.keys() if c in df.columns]
            df_display = df[cols].rename(columns=column_map)

            if 'Authors' in df_display.columns:
                df_display['Authors'] = df_display['Authors'].apply(lambda x: ', '.join(x) if isinstance(x,(list,tuple)) else x)
            
            # DOI Link Logic
            if 'DOI' in df_display.columns:
                df_display['DOI_Link'] = df_display['DOI'].apply(
                    lambda x: f"https://doi.org/{x}" if x and not str(x).startswith('http') else x
                )

            # 2. Filtering
            # Year Filter
            if 'Year' in df_display.columns:
                df_display['Year'] = pd.to_numeric(df_display['Year'], errors='coerce')
                df_display = df_display[
                    (df_display['Year'] >= year_min) & (df_display['Year'] <= year_max) | df_display['Year'].isna()
                ]
            
            # OA Filter
            if oa_filter == 'Open Access Only' and 'OA' in df_display.columns:
                df_display = df_display[df_display['OA'].apply(lambda v: bool(v) if pd.notna(v) else False)]
            
            # Citation Filter
            if 'Cites' in df_display.columns:
                df_display['Cites'] = pd.to_numeric(df_display['Cites'], errors='coerce').fillna(0)
                df_display = df_display[df_display['Cites'] >= min_citations]

            # Source Filter
            if 'Source' in df_display.columns and sources:
                df_display = df_display[df_display['Source'].isin(sources)]

            st.success(f"Found {len(df_display)} papers matching criteria.")

            # --- TABS INTERFACE ---
            tab1, tab2 = st.tabs(["📄 List View", "📊 Analytics Dashboard"])

            # --- TAB 1: LIST VIEW ---
            with tab1:
                # Layout
                if st.session_state.get('pdf_preview_checkbox', True):
                    left, right = st.columns([1.8, 1]) 
                else:
                    left = st.container()
                    right = None

                selected_row_data = {}

                with left:
                    # Config columns
                    column_config = {
                        "PDF": st.column_config.LinkColumn("PDF", display_text="Open PDF"),
                        "URL": st.column_config.LinkColumn("URL", display_text="Source"),
                        "DOI_Link": st.column_config.LinkColumn("DOI", display_text=r"doi.org/(.*)"),
                        "Cites": st.column_config.ProgressColumn("Impact", format="%d", min_value=0, max_value=df_display['Cites'].max() if not df_display.empty else 100),
                        "Year": st.column_config.NumberColumn("Year", format="%d"),
                        "Abstract": st.column_config.TextColumn("Abstract", width="large", disabled=True), 
                    }

                    display_cols = ['Title', 'Cites', 'Year', 'Venue', 'Authors', 'Source', 'PDF', 'DOI_Link']
                    display_cols = [c for c in display_cols if c in df_display.columns]

                    event = st.dataframe(
                        df_display[display_cols],
                        column_config=column_config,
                        use_container_width=True,
                        hide_index=True,
                        on_select="rerun",
                        selection_mode="single-row",
                        height=600
                    )
                    
                    if event.selection.rows:
                        idx = event.selection.rows[0]
                        selected_row_data = df_display.iloc[idx].to_dict()

                    # Exports
                    col_dl1, col_dl2 = st.columns(2)
                    csv = df_display.to_csv(index=False).encode('utf-8-sig')
                    col_dl1.download_button("📥 Download CSV", csv, file_name="results.csv", mime='text/csv', use_container_width=True)
                    
                    bibtxt = "\n".join([to_bibtex_entry(row) for _, row in df_display.iterrows()])
                    col_dl2.download_button("📚 Download BibTeX", data=bibtxt.encode('utf-8'), file_name="citations.bib", mime='text/plain', use_container_width=True)

                # Right Panel Details
                if right is not None:
                    with right:
                        if selected_row_data:
                            st.info("📌 **Selected Paper Details**")
                            st.markdown(f"### {selected_row_data.get('Title')}")
                            st.markdown(f"**👥 Authors:** {selected_row_data.get('Authors')}")
                            st.markdown(f"**📅 Year:** {selected_row_data.get('Year')} | **🏛️ Venue:** {selected_row_data.get('Venue')}")
                            st.markdown(f"**🔥 Citations:** {selected_row_data.get('Cites')}")
                            
                            with st.expander("📖 **Abstract**", expanded=True):
                                st.write(selected_row_data.get('Abstract', 'No abstract available.'))

                            st.markdown("---")
                            # PDF Preview
                            pdf_url = selected_row_data.get('PDF')
                            if pdf_url:
                                st.markdown("##### 📄 PDF Preview")
                                try:
                                    st.components.v1.iframe(pdf_url, height=500, scrolling=True)
                                except:
                                    st.write(f"[Open PDF in new tab]({pdf_url})")
                            else:
                                st.warning("No direct PDF link found.")
                        else:
                            st.info("👈 Select a paper from the list to view Abstract & Details.")

            # --- TAB 2: ANALYTICS DASHBOARD ---
            with tab2:
                st.subheader("📊 Research Trends")
                
                if not df_display.empty:
                    col_chart1, col_chart2 = st.columns(2)
                    
                    with col_chart1:
                        st.markdown("**📅 Publications over Time**")
                        # Bar chart for Year
                        chart_year = alt.Chart(df_display).mark_bar().encode(
                            x=alt.X('Year:O', axis=alt.Axis(labelAngle=0)),
                            y='count()',
                            color=alt.value('#3b82f6'),
                            tooltip=['Year', 'count()']
                        ).interactive()
                        st.altair_chart(chart_year, use_container_width=True)

                    with col_chart2:
                        st.markdown("**🏆 Top Venues / Journals**")
                        # Top Venues
                        venue_counts = df_display['Venue'].value_counts().reset_index()
                        venue_counts.columns = ['Venue', 'Count']
                        venue_counts = venue_counts[venue_counts['Venue'] != ''] # remove empty
                        
                        chart_venue = alt.Chart(venue_counts.head(10)).mark_bar().encode(
                            x='Count',
                            y=alt.Y('Venue', sort='-x'),
                            color=alt.value('#ef4444'),
                            tooltip=['Venue', 'Count']
                        ).interactive()
                        st.altair_chart(chart_venue, use_container_width=True)
                    
                    st.markdown("---")
                    st.markdown("**📈 Citation Impact (Cites vs Year)**")
                    
                    chart_scatter = alt.Chart(df_display).mark_circle(size=60).encode(
                        x=alt.X('Year:O'),
                        y='Cites:Q',
                        color='Source',
                        tooltip=['Title', 'Authors', 'Cites', 'Year']
                    ).interactive()
                    st.altair_chart(chart_scatter, use_container_width=True)

                else:
                    st.write("No data available for visualization.")

    # Footer
    st.markdown("---")
    st.caption("Developed by Oxyec. Powered by Streamlit & Python.")

if __name__ == "__main__":
    from streamlit.web import cli as stcli
    if "streamlit" not in sys.modules:
        sys.argv = ["streamlit", "run", sys.argv[0], "--server.headless", "true"]
        sys.exit(stcli.main())
    else:
        main()