import asyncio
import concurrent.futures
import hashlib
import math
from datetime import datetime

import altair as alt
import pandas as pd
import streamlit as st

from src.app_utils import (
    CURRENT_YEAR,
    build_author_counts,
    build_markdown_brief,
    build_research_brief,
    build_source_counts,
    clean_text,
    deduplicate_results,
    extract_top_keywords,
    load_persisted_state,
    persist_state,
    prepare_dataframe,
    state_persistence_enabled,
    to_bibtex_entry,
)
from src.search_sources import search_all_sources

st.set_page_config(page_title="Academic Research Assistant", page_icon="A", layout="wide")


def run_async(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(lambda: asyncio.run(coro)).result()


def persist_state_from_session():
    persist_state(
        st.session_state.get("saved_searches", []),
        st.session_state.get("bookmarks", {}),
    )


def apply_sort(df, mode):
    if mode == "Relevance score":
        return df.sort_values(by=["Score", "Cites"], ascending=[False, False], kind="mergesort")
    if mode == "Most cited":
        return df.sort_values(by=["Cites", "Score"], ascending=[False, False], kind="mergesort")
    if mode == "Newest first":
        return df.sort_values(by=["Year", "Score"], ascending=[False, False], kind="mergesort", na_position="last")
    if mode == "Oldest first":
        return df.sort_values(by=["Year", "Score"], ascending=[True, False], kind="mergesort", na_position="last")
    return df.sort_values(by=["Title"], ascending=[True], kind="mergesort")


def init_session_state():
    if "state_loaded" not in st.session_state:
        persisted = load_persisted_state()
        st.session_state["saved_searches"] = persisted["saved_searches"]
        st.session_state["bookmarks"] = persisted["bookmarks"]
        st.session_state["state_loaded"] = True

    st.session_state.setdefault("raw_results", [])
    st.session_state.setdefault("source_stats", [])
    st.session_state.setdefault("last_query", "")


def inject_styles(ui_mode="Auto"):
    if ui_mode == "Dark":
        mode_block = """
        :root {
            --background-color: #0b1220;
            --secondary-background-color: #111c2f;
            --text-color: #e7edf8;
            --primary-color: #ff4d57;
            --app-bg-start: #0b1220;
            --app-bg-mid: #0d1626;
            --app-bg-end: #0a111c;
            --sidebar-bg: #101b2c;
            --panel-border: rgba(127, 156, 196, 0.28);
            --hero-border: rgba(129, 167, 214, 0.32);
            --hero-grad-a: #13253b;
            --hero-grad-b: #1c3653;
            --hero-grad-c: #275286;
            --hero-text: #edf4ff;
        }
        """
        component_overrides = ""
    elif ui_mode == "Light":
        mode_block = """
        :root {
            --background-color: #f2f6fb;
            --secondary-background-color: #ffffff;
            --text-color: #14243a;
            --primary-color: #ff4d57;
            --app-bg-start: #e9f1fb;
            --app-bg-mid: #f3f8ff;
            --app-bg-end: #ffffff;
            --sidebar-bg: #edf3fa;
            --panel-border: rgba(35, 62, 92, 0.14);
            --hero-border: rgba(215, 229, 244, 0.8);
            --hero-grad-a: #0f2740;
            --hero-grad-b: #1f4c77;
            --hero-grad-c: #2d6ba0;
            --hero-text: #f7fbff;
        }
        """
        component_overrides = """
        [data-testid="stAppViewContainer"],
        [data-testid="stSidebar"] {
            color: #14243a !important;
        }
        [data-testid="stWidgetLabel"],
        [data-testid="stWidgetLabel"] p,
        [data-testid="stWidgetLabel"] span,
        [data-testid="stCaptionContainer"] p {
            color: #233a56 !important;
            opacity: 1 !important;
        }
        div[data-baseweb="input"] > div,
        div[data-baseweb="select"] > div,
        div[data-baseweb="base-input"] > div {
            background: #ffffff !important;
            color: #14243a !important;
            border-color: rgba(35, 62, 92, 0.22) !important;
        }
        div[data-baseweb="input"] > div > div,
        div[data-baseweb="select"] > div > div,
        div[data-baseweb="base-input"] > div > div {
            background: #ffffff !important;
            color: #14243a !important;
        }
        div[data-baseweb="input"] input,
        div[data-baseweb="base-input"] input,
        div[data-baseweb="select"] input {
            color: #14243a !important;
        }
        div[data-baseweb="input"] button,
        div[data-baseweb="base-input"] button,
        div[data-baseweb="select"] button {
            background: #ffffff !important;
            color: #17324e !important;
            border-color: rgba(35, 62, 92, 0.20) !important;
        }
        div[data-baseweb="tag"] {
            background: #e9f0fb !important;
            color: #17324e !important;
            border-color: rgba(35, 62, 92, 0.20) !important;
        }
        """
    else:
        mode_block = """
        :root {
            --app-bg-start: var(--secondary-background-color);
            --app-bg-mid: var(--background-color);
            --app-bg-end: var(--background-color);
            --sidebar-bg: var(--secondary-background-color);
            --panel-border: rgba(127, 127, 127, 0.28);
            --hero-border: rgba(127, 127, 127, 0.32);
            --hero-grad-a: #0f2740;
            --hero-grad-b: #1f4c77;
            --hero-grad-c: #2d6ba0;
            --hero-text: #f7fbff;
        }
        html[data-theme="dark"], body[data-theme="dark"], [data-theme="dark"] {
            --app-bg-start: #0b1220;
            --app-bg-mid: #0d1626;
            --app-bg-end: #0a111c;
            --sidebar-bg: #101b2c;
            --panel-border: rgba(127, 156, 196, 0.28);
            --hero-border: rgba(129, 167, 214, 0.32);
            --hero-grad-a: #13253b;
            --hero-grad-b: #1c3653;
            --hero-grad-c: #275286;
            --hero-text: #edf4ff;
        }
        html[data-theme="light"], body[data-theme="light"], [data-theme="light"] {
            --app-bg-start: #eef5ff;
            --app-bg-mid: #f7fbff;
            --app-bg-end: #ffffff;
            --sidebar-bg: #f4f7fb;
            --panel-border: rgba(35, 62, 92, 0.14);
            --hero-border: rgba(215, 229, 244, 0.8);
            --hero-grad-a: #0f2740;
            --hero-grad-b: #1f4c77;
            --hero-grad-c: #2d6ba0;
            --hero-text: #f7fbff;
        }
        """
        component_overrides = ""

    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&family=Source+Sans+3:wght@400;600&display=swap');
        {mode_block}
        html, body, [data-testid="stAppViewContainer"], [data-testid="stSidebar"] {{
            font-family: "Source Sans 3", sans-serif;
        }}
        h1, h2, h3, .hero-title {{
            font-family: "Space Grotesk", sans-serif;
            letter-spacing: -0.02em;
        }}
        [data-testid="stAppViewContainer"] {{
            color: var(--text-color);
            background: radial-gradient(circle at 18% 8%, var(--app-bg-start) 0%, var(--app-bg-mid) 38%, var(--app-bg-end) 78%);
        }}
        [data-testid="stSidebar"] {{
            background: var(--sidebar-bg);
            border-right: 1px solid var(--panel-border);
        }}
        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] span {{
            color: var(--text-color) !important;
            opacity: 0.96;
        }}
        [data-testid="stHeader"] {{
            background: transparent;
        }}
        .block-container {{
            padding-top: 1.0rem;
            padding-bottom: 2rem;
        }}
        [data-testid="stVerticalBlock"] > div:has(> div[data-testid="stContainer"]) {{
            border-radius: 12px;
        }}
        div[data-testid="stContainer"] {{
            border-color: var(--panel-border) !important;
        }}
        .hero-shell {{
            border: 1px solid var(--hero-border);
            background: linear-gradient(120deg, var(--hero-grad-a) 0%, var(--hero-grad-b) 60%, var(--hero-grad-c) 100%);
            border-radius: 16px;
            padding: 22px 24px;
            margin-bottom: 14px;
            color: var(--hero-text);
        }}
        .hero-kicker {{
            text-transform: uppercase;
            letter-spacing: 0.08em;
            font-size: 0.78rem;
            opacity: 0.9;
            margin-bottom: 4px;
        }}
        .hero-title {{
            font-size: 1.9rem;
            line-height: 1.15;
            margin: 0 0 8px 0;
        }}
        .hero-copy {{
            margin: 0;
            font-size: 1rem;
            opacity: 0.95;
        }}
        {component_overrides}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar_tools():
    with st.sidebar:
        st.header("Workspace")
        st.caption("Tools and credentials")
        ui_mode = st.radio(
            "UI mode",
            options=["Auto", "Dark", "Light"],
            index=0,
            horizontal=True,
            key="ui_mode_input",
        )

        with st.container(border=True):
            st.markdown("**API Access**")
            ss_key = st.text_input("Semantic Scholar key", type="password", key="ss_key_input")
            g_key = st.text_input("Google API key", type="password", key="google_key_input")
            g_cx = st.text_input("Google CX ID", type="password", key="google_cx_input")
            email = st.text_input("Crossref email", value="researcher@example.com", key="crossref_email_input")

        with st.container(border=True):
            st.markdown("**Reading List**")
            bookmark_count = len(st.session_state["bookmarks"])
            if state_persistence_enabled():
                st.caption(f"{bookmark_count} saved papers")
            else:
                st.caption(f"{bookmark_count} papers in this session")
                st.caption("Persistence is disabled for deployment safety.")
            if bookmark_count > 0:
                bookmark_df = pd.DataFrame(st.session_state["bookmarks"].values())
                st.download_button(
                    "Download Reading List CSV",
                    bookmark_df.to_csv(index=False).encode("utf-8"),
                    "reading_list.csv",
                    "text/csv",
                    width="stretch",
                )
            else:
                st.caption("No papers saved yet.")

    return {
        "keys": {"ss": ss_key, "google": g_key, "cx": g_cx},
        "email": email,
        "ui_mode": ui_mode,
    }


def render_search_header():
    st.markdown(
        """
        <div class="hero-shell">
            <div class="hero-kicker">Academic Discovery Studio</div>
            <h1 class="hero-title">Search faster, compare sources, and build a curated reading list.</h1>
            <p class="hero-copy">Use the query bar below to search all selected databases in parallel.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.container(border=True):
        row1_col1, row1_col2 = st.columns([5, 1.2])
        with row1_col1:
            query = st.text_input(
                "Research topic",
                key="query_input",
                placeholder="example: retrieval augmented generation in healthcare",
            )
        with row1_col2:
            st.write("")
            search_btn = st.button("Start Search", type="primary", width="stretch")

        row2_col1, row2_col2 = st.columns([3.2, 1.4])
        with row2_col1:
            sources = st.multiselect(
                "Sources",
                ["Semantic Scholar", "OpenAlex", "ArXiv", "Crossref", "Google Custom Search"],
                default=["Semantic Scholar", "OpenAlex", "ArXiv"],
                key="sources_input",
            )
        with row2_col2:
            limit = st.slider("Results per source", 5, 100, 20, step=5, key="limit_input")

    return {
        "query": query,
        "sources": sources,
        "limit": limit,
        "search_btn": search_btn,
    }


def _map_legacy_year_pct_to_range(value):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return None
    year_floor = 1990
    year_span = max(CURRENT_YEAR - year_floor, 1)
    start = year_floor + round(((int(value[0]) - 20) / 80) * year_span)
    end = year_floor + round(((int(value[1]) - 20) / 80) * year_span)
    start = max(year_floor, min(start, CURRENT_YEAR))
    end = max(start, min(end, CURRENT_YEAR))
    return (start, end)


def _hydrate_logical_slider_state(selected_source_count):
    if "year_range_input" not in st.session_state:
        mapped = None
        if "year_range_pct_input" in st.session_state:
            mapped = _map_legacy_year_pct_to_range(st.session_state.get("year_range_pct_input"))
        st.session_state["year_range_input"] = mapped or (max(2000, CURRENT_YEAR - 10), CURRENT_YEAR)

    if "fuzzy_threshold_pct_input" not in st.session_state:
        try:
            if "fuzzy_threshold_input" in st.session_state:
                pct_value = float(st.session_state.get("fuzzy_threshold_input", 0.90)) * 100.0
            else:
                pct_value = float(st.session_state.get("fuzzy_threshold_pct_input", 90))
            st.session_state["fuzzy_threshold_pct_input"] = int(round(max(40.0, min(100.0, pct_value))))
        except Exception:
            st.session_state["fuzzy_threshold_pct_input"] = 90

    if "min_source_count_input" not in st.session_state and "min_source_pct_input" in st.session_state:
        try:
            pct_value = float(st.session_state.get("min_source_pct_input", 20))
            required = max(1, math.ceil((pct_value / 100.0) * max(selected_source_count, 1)))
            st.session_state["min_source_count_input"] = min(required, max(selected_source_count, 1))
        except Exception:
            st.session_state["min_source_count_input"] = 1

    weight_keys = [
        ("text_weight_input", "text_weight_pct_input", 0.55),
        ("citation_weight_input", "citation_weight_pct_input", 0.25),
        ("recency_weight_input", "recency_weight_pct_input", 0.20),
    ]
    for logical_key, pct_key, default_value in weight_keys:
        if logical_key not in st.session_state and pct_key in st.session_state:
            try:
                st.session_state[logical_key] = max(0.0, min(1.0, float(st.session_state[pct_key]) / 100.0))
            except Exception:
                st.session_state[logical_key] = default_value

    if "year_range_input" in st.session_state:
        year_value = st.session_state.get("year_range_input")
        if isinstance(year_value, list):
            year_value = tuple(year_value)
        if not isinstance(year_value, tuple) or len(year_value) != 2:
            year_value = (max(2000, CURRENT_YEAR - 10), CURRENT_YEAR)
        start = max(1990, min(int(year_value[0]), CURRENT_YEAR))
        end = max(start, min(int(year_value[1]), CURRENT_YEAR))
        st.session_state["year_range_input"] = (start, end)

    try:
        current_fuzzy_pct = int(st.session_state.get("fuzzy_threshold_pct_input", 90))
    except Exception:
        current_fuzzy_pct = 90
    st.session_state["fuzzy_threshold_pct_input"] = max(40, min(current_fuzzy_pct, 100))

    try:
        current_min_source = int(st.session_state.get("min_source_count_input", 1))
    except Exception:
        current_min_source = 1
    st.session_state["min_source_count_input"] = max(1, min(current_min_source, selected_source_count))


def normalize_setup_config(config):
    if not isinstance(config, dict):
        return {}

    normalized = dict(config)
    source_count = len(normalized.get("sources_input", []))
    source_count = max(source_count, 1)

    if "year_range_input" not in normalized and "year_range_pct_input" in normalized:
        mapped_years = _map_legacy_year_pct_to_range(normalized.get("year_range_pct_input"))
        if mapped_years:
            normalized["year_range_input"] = mapped_years

    if "fuzzy_threshold_pct_input" not in normalized:
        if "fuzzy_threshold_input" in normalized:
            try:
                normalized["fuzzy_threshold_pct_input"] = int(
                    round(max(40.0, min(100.0, float(normalized["fuzzy_threshold_input"]) * 100.0)))
                )
            except Exception:
                normalized["fuzzy_threshold_pct_input"] = 90
        else:
            normalized["fuzzy_threshold_pct_input"] = 90
    else:
        try:
            normalized["fuzzy_threshold_pct_input"] = int(
                round(max(40.0, min(100.0, float(normalized["fuzzy_threshold_pct_input"]))))
            )
        except Exception:
            normalized["fuzzy_threshold_pct_input"] = 90

    if "min_source_count_input" not in normalized and "min_source_pct_input" in normalized:
        try:
            pct_value = float(normalized["min_source_pct_input"])
            normalized["min_source_count_input"] = min(
                max(1, math.ceil((pct_value / 100.0) * source_count)),
                source_count,
            )
        except Exception:
            normalized["min_source_count_input"] = 1

    legacy_weight_pairs = [
        ("text_weight_input", "text_weight_pct_input", 0.55),
        ("citation_weight_input", "citation_weight_pct_input", 0.25),
        ("recency_weight_input", "recency_weight_pct_input", 0.20),
    ]
    for logical_key, pct_key, default_value in legacy_weight_pairs:
        if logical_key not in normalized and pct_key in normalized:
            try:
                normalized[logical_key] = max(0.0, min(1.0, float(normalized[pct_key]) / 100.0))
            except Exception:
                normalized[logical_key] = default_value

    return normalized


def render_controls(selected_source_count):
    selected_source_count = max(int(selected_source_count or 1), 1)
    _hydrate_logical_slider_state(selected_source_count)

    with st.container(border=True):
        st.subheader("Filters and Ranking")
        col1, col2, col3 = st.columns(3)

        with col1:
            year_range = st.slider(
                "Publication year range",
                1990,
                CURRENT_YEAR,
                key="year_range_input",
            )
            min_citations = st.number_input("Minimum citations", 0, 100000, 0, step=10, key="min_citations_input")
            oa_filter = st.checkbox("Open access only", value=False, key="oa_filter_input")
            min_source_count = st.slider(
                "Minimum source agreement",
                min_value=1,
                max_value=selected_source_count,
                key="min_source_count_input",
                help="Require each paper to appear in at least this many selected sources.",
            )

        with col2:
            dedupe_enabled = st.checkbox("Smart deduplication", value=True, key="dedupe_input")
            fuzzy_dedupe = st.checkbox("Fuzzy title merge", value=False, key="fuzzy_dedupe_input")
            fuzzy_threshold_pct = st.slider(
                "Fuzzy dedupe threshold (%)",
                40,
                100,
                key="fuzzy_threshold_pct_input",
                disabled=not fuzzy_dedupe,
                help="Higher values are stricter. 90 is a good default.",
            )
            fuzzy_threshold = fuzzy_threshold_pct / 100.0
            sort_mode = st.selectbox(
                "Sort by",
                ["Relevance score", "Most cited", "Newest first", "Oldest first", "Title A-Z"],
                key="sort_mode_input",
            )
            max_rows = st.slider("Max visible rows", 20, 500, 200, step=20, key="max_rows_input")

        with col3:
            text_weight = st.slider("Text relevance weight", 0.0, 1.0, 0.55, step=0.01, key="text_weight_input")
            citation_weight = st.slider("Citation weight", 0.0, 1.0, 0.25, step=0.01, key="citation_weight_input")
            recency_weight = st.slider("Recency weight", 0.0, 1.0, 0.20, step=0.01, key="recency_weight_input")
            st.caption(f"Weight sum: {text_weight + citation_weight + recency_weight:.2f} (auto-normalized)")

        st.markdown("**Text Filters**")
        t1, t2, t3 = st.columns(3)
        with t1:
            title_filter = st.text_input("Title contains", key="title_filter_input")
        with t2:
            author_filter = st.text_input("Author contains", key="author_filter_input")
        with t3:
            venue_filter = st.text_input("Venue contains", key="venue_filter_input")

    return {
        "year_range": year_range,
        "min_citations": int(min_citations),
        "oa_filter": oa_filter,
        "min_source_count": int(min_source_count),
        "dedupe_enabled": dedupe_enabled,
        "fuzzy_dedupe": fuzzy_dedupe,
        "fuzzy_threshold": float(fuzzy_threshold),
        "fuzzy_threshold_pct": int(fuzzy_threshold_pct),
        "sort_mode": sort_mode,
        "max_rows": int(max_rows),
        "score_weights": (text_weight, citation_weight, recency_weight),
        "title_filter": clean_text(title_filter),
        "author_filter": clean_text(author_filter),
        "venue_filter": clean_text(venue_filter),
    }


def render_setup_manager(query, sources, limit, controls):
    with st.container(border=True):
        st.subheader("Saved Setups")
        c1, c2, c3 = st.columns([1.6, 1, 1])

        saved_searches = st.session_state["saved_searches"]
        selected_idx = None
        if saved_searches:
            with c1:
                selected_idx = st.selectbox(
                    "Choose setup",
                    options=list(range(len(saved_searches))),
                    format_func=lambda idx: saved_searches[idx]["label"],
                    key="saved_setup_idx",
                )
        else:
            with c1:
                st.caption("No saved setups yet.")

        with c2:
            save_setup = st.button("Save Current Setup", width="stretch")
        with c3:
            load_setup = st.button("Load Selected Setup", width="stretch", disabled=selected_idx is None)

    if save_setup and clean_text(query):
        item = {
            "label": f"{clean_text(query)} ({datetime.now().strftime('%Y-%m-%d %H:%M')})",
            "config": {
                "query_input": clean_text(query),
                "sources_input": list(sources),
                "limit_input": int(limit),
                "year_range_input": tuple(controls["year_range"]),
                "min_citations_input": controls["min_citations"],
                "oa_filter_input": controls["oa_filter"],
                "dedupe_input": controls["dedupe_enabled"],
                "fuzzy_dedupe_input": controls["fuzzy_dedupe"],
                "fuzzy_threshold_pct_input": controls["fuzzy_threshold_pct"],
                "min_source_count_input": controls["min_source_count"],
                "sort_mode_input": controls["sort_mode"],
                "text_weight_input": controls["score_weights"][0],
                "citation_weight_input": controls["score_weights"][1],
                "recency_weight_input": controls["score_weights"][2],
                "title_filter_input": controls["title_filter"],
                "author_filter_input": controls["author_filter"],
                "venue_filter_input": controls["venue_filter"],
                "max_rows_input": controls["max_rows"],
            },
        }
        st.session_state["saved_searches"].insert(0, item)
        st.session_state["saved_searches"] = st.session_state["saved_searches"][:20]
        persist_state_from_session()
        st.toast("Setup saved")

    if load_setup and selected_idx is not None:
        config = normalize_setup_config(st.session_state["saved_searches"][selected_idx]["config"])
        for key, value in config.items():
            st.session_state[key] = value
        st.rerun()


def perform_search(search_input, auth_input):
    query = clean_text(search_input["query"])
    if not search_input["search_btn"]:
        return
    if not query:
        st.toast("Please enter a search term.")
        return

    progress_bar = st.progress(0)

    def update_progress(value):
        progress_bar.progress(value)

    with st.spinner(f"Searching for '{query}' across sources..."):
        raw_results, source_stats = run_async(
            search_all_sources(
                query,
                search_input["limit"],
                search_input["sources"],
                auth_input["keys"],
                auth_input["email"],
                progress_callback=update_progress,
            )
        )
        st.session_state["raw_results"] = raw_results
        st.session_state["source_stats"] = source_stats
        st.session_state["last_query"] = query

    progress_bar.empty()


def render_output(df, raw_results, rows, source_stats, active_query, max_rows):
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Raw Rows", str(len(raw_results)))
    m2.metric("After Dedupe", str(len(rows)))
    m3.metric("Visible Rows", str(len(df)))
    m4.metric("Open Access %", f"{df['OA'].mean() * 100:.1f}%")
    m5.metric("Median Cites", str(int(df["Cites"].median())))

    st.info(build_research_brief(df, active_query))
    brief_markdown = build_markdown_brief(df, active_query, source_stats=source_stats, top_n=12)
    st.download_button("Download Research Brief (Markdown)", brief_markdown, "research_brief.md", "text/markdown", width="stretch")

    tab1, tab2, tab3, tab4 = st.tabs(["Results", "Analytics", "Reading List", "Diagnostics"])
    df_display = df.head(max_rows).copy()

    with tab1:
        col_list, col_details = st.columns([1.8, 1.0])
        with col_list:
            table_event = st.dataframe(
                df_display[["Title", "Score", "Cites", "Year", "Venue", "Authors", "SourceCount", "Source", "PDF", "URL"]],
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                height=620,
                width="stretch",
                column_config={
                    "URL": st.column_config.LinkColumn("Source", display_text="Open"),
                    "PDF": st.column_config.LinkColumn("PDF", display_text="PDF"),
                    "Cites": st.column_config.ProgressColumn(
                        "Cites",
                        format="%d",
                        min_value=0,
                        max_value=int(df_display["Cites"].max()) if int(df_display["Cites"].max()) > 0 else 100,
                    ),
                    "Score": st.column_config.NumberColumn("Score", format="%.3f"),
                    "SourceCount": st.column_config.NumberColumn("Sources", format="%d"),
                },
            )

            e1, e2, e3 = st.columns(3)
            e1.download_button("CSV", df.to_csv(index=False).encode("utf-8"), "results.csv", "text/csv", width="stretch")
            e2.download_button(
                "JSON",
                df.to_json(orient="records", indent=2).encode("utf-8"),
                "results.json",
                "application/json",
                width="stretch",
            )
            bib = "\n".join([to_bibtex_entry(row) for _, row in df.iterrows()])
            e3.download_button("BibTeX", bib, "references.bib", "text/plain", width="stretch")

        with col_details:
            if table_event.selection.rows:
                selected_row = df_display.iloc[table_event.selection.rows[0]]
                row_key = hashlib.md5(selected_row["RecordId"].encode("utf-8")).hexdigest()[:10]
                st.markdown(f"### {selected_row['Title']}")
                st.caption(f"{selected_row['Year']} | {selected_row['Venue']} | {selected_row['Source']}")
                st.write(f"Authors: {selected_row['Authors']}")
                st.write(f"Citations: {selected_row['Cites']} | Score: {selected_row['Score']:.3f}")
                if selected_row["DOI"]:
                    st.write(f"DOI: {selected_row['DOI']}")

                abstract_text = clean_text(selected_row.get("Abstract"))
                if abstract_text:
                    with st.expander("Abstract", expanded=True):
                        st.write(abstract_text)

                l1, l2 = st.columns(2)
                if selected_row["URL"]:
                    l1.link_button("Open Source", selected_row["URL"], width="stretch")
                if selected_row["PDF"]:
                    l2.link_button("Open PDF", selected_row["PDF"], width="stretch")

                is_saved = selected_row["RecordId"] in st.session_state["bookmarks"]
                label = "Remove from Reading List" if is_saved else "Add to Reading List"
                if st.button(label, key=f"bookmark_{row_key}", width="stretch"):
                    if is_saved:
                        st.session_state["bookmarks"].pop(selected_row["RecordId"], None)
                    else:
                        st.session_state["bookmarks"][selected_row["RecordId"]] = selected_row.to_dict()
                    persist_state_from_session()
                    st.rerun()
            else:
                st.info("Select a row to inspect details.")

    with tab2:
        c1, c2 = st.columns(2)
        with c1:
            year_df = df[df["Year"].notna()].copy()
            if not year_df.empty:
                chart_year = (
                    alt.Chart(year_df)
                    .mark_bar()
                    .encode(x=alt.X("Year:O", title="Year"), y=alt.Y("count()", title="Publications"), tooltip=["Year", "count()"])
                    .interactive()
                )
                st.altair_chart(chart_year, width="stretch")

        with c2:
            src_df = build_source_counts(df)
            if not src_df.empty:
                pie = (
                    alt.Chart(src_df)
                    .mark_arc(innerRadius=60)
                    .encode(theta=alt.Theta("Count:Q"), color=alt.Color("Source:N"), tooltip=["Source", "Count"])
                )
                st.altair_chart(pie, width="stretch")

        c3, c4 = st.columns(2)
        with c3:
            author_df = build_author_counts(df, top_n=12)
            if not author_df.empty:
                author_chart = (
                    alt.Chart(author_df)
                    .mark_bar()
                    .encode(x=alt.X("Count:Q"), y=alt.Y("Author:N", sort="-x"), tooltip=["Author", "Count"])
                )
                st.altair_chart(author_chart, width="stretch")

        with c4:
            keywords = extract_top_keywords(df["Title"], top_n=12)
            if keywords:
                keyword_df = pd.DataFrame(keywords, columns=["Keyword", "Count"])
                keyword_chart = (
                    alt.Chart(keyword_df)
                    .mark_bar()
                    .encode(x=alt.X("Count:Q"), y=alt.Y("Keyword:N", sort="-x"), tooltip=["Keyword", "Count"])
                )
                st.altair_chart(keyword_chart, width="stretch")

    with tab3:
        bookmarks = st.session_state["bookmarks"]
        if not bookmarks:
            st.info("Your reading list is empty.")
        else:
            reading_df = pd.DataFrame(bookmarks.values())
            st.dataframe(
                reading_df[["Title", "Authors", "Year", "Venue", "Cites", "Source", "URL"]],
                hide_index=True,
                width="stretch",
            )
            r1, r2 = st.columns(2)
            r1.download_button(
                "Download Reading List CSV",
                reading_df.to_csv(index=False).encode("utf-8"),
                "reading_list.csv",
                "text/csv",
                width="stretch",
            )
            rbib = "\n".join([to_bibtex_entry(row) for _, row in reading_df.iterrows()])
            r2.download_button("Download Reading List BibTeX", rbib, "reading_list.bib", "text/plain", width="stretch")
            if st.button("Clear Reading List", width="stretch"):
                st.session_state["bookmarks"] = {}
                persist_state_from_session()
                st.rerun()

    with tab4:
        if source_stats:
            stats_df = pd.DataFrame(source_stats)
            stats_df["duration_sec"] = stats_df["duration_sec"].apply(lambda value: round(float(value), 2))
            st.dataframe(stats_df[["source", "result_count", "duration_sec", "status", "error"]], hide_index=True, width="stretch")
        else:
            st.info("No source diagnostics yet.")
        st.markdown("**Top Picks**")
        st.dataframe(df[["Title", "Score", "Cites", "Year", "Source"]].head(8), hide_index=True, width="stretch")


def main():
    init_session_state()

    auth_input = render_sidebar_tools()
    inject_styles(auth_input.get("ui_mode", "Auto"))
    search_input = render_search_header()
    controls = render_controls(len(search_input["sources"]))
    render_setup_manager(search_input["query"], search_input["sources"], search_input["limit"], controls)
    perform_search(search_input, auth_input)

    raw_results = st.session_state["raw_results"]
    if not raw_results:
        st.info("Run a search to see results.")
        return

    active_query = st.session_state["last_query"] or clean_text(search_input["query"])
    source_stats = st.session_state["source_stats"]

    rows = (
        deduplicate_results(
            raw_results,
            fuzzy_title=controls["fuzzy_dedupe"],
            fuzzy_threshold=controls["fuzzy_threshold"],
        )
        if controls["dedupe_enabled"]
        else raw_results
    )

    df = prepare_dataframe(rows, active_query, score_weights=controls["score_weights"])
    if df.empty:
        st.warning("No records were returned from data sources.")
        return

    year_start, year_end = controls["year_range"]
    df = df[(df["Year"].isna()) | ((df["Year"] >= year_start) & (df["Year"] <= year_end))]
    df = df[df["Cites"] >= controls["min_citations"]]
    selected_source_count = max(len(search_input["sources"]), 1)
    min_required_sources = max(1, min(controls["min_source_count"], selected_source_count))
    df = df[df["SourceCount"] >= min_required_sources]
    if controls["oa_filter"]:
        df = df[df["OA"]]
    if controls["title_filter"]:
        df = df[df["Title"].str.contains(controls["title_filter"], case=False, na=False)]
    if controls["author_filter"]:
        df = df[df["Authors"].str.contains(controls["author_filter"], case=False, na=False)]
    if controls["venue_filter"]:
        df = df[df["Venue"].str.contains(controls["venue_filter"], case=False, na=False)]

    df = apply_sort(df, controls["sort_mode"])
    if df.empty:
        st.warning("No papers found after filtering.")
        return

    render_output(df, raw_results, rows, source_stats, active_query, controls["max_rows"])


if __name__ == "__main__":
    main()
