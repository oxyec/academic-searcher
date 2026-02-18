import hashlib
import json
import math
import os
import re
from collections import Counter
from datetime import datetime

import pandas as pd

CURRENT_YEAR = datetime.now().year
STATE_FILE = ".academic_search_state.json"
STOPWORDS = {
    "about",
    "after",
    "again",
    "also",
    "among",
    "been",
    "being",
    "between",
    "both",
    "can",
    "could",
    "data",
    "during",
    "each",
    "from",
    "have",
    "into",
    "more",
    "most",
    "much",
    "paper",
    "results",
    "study",
    "than",
    "that",
    "their",
    "there",
    "these",
    "this",
    "those",
    "using",
    "with",
    "without",
}


def clean_text(text):
    if text is None:
        return ""
    return re.sub(r"\s+", " ", str(text)).strip()


def normalize_year(value):
    try:
        if pd.isna(value) or value in ("", None):
            return None
        return int(float(str(value)))
    except Exception:
        return None


def normalize_int(value):
    try:
        if pd.isna(value) or value in ("", None):
            return 0
        return int(float(value))
    except Exception:
        return 0


def normalize_doi(value):
    doi = clean_text(value).lower()
    if not doi:
        return ""
    doi = doi.replace("https://doi.org/", "")
    doi = doi.replace("http://doi.org/", "")
    return doi


def title_fingerprint(title):
    cleaned = re.sub(r"[^a-z0-9 ]+", " ", clean_text(title).lower())
    tokens = [token for token in cleaned.split() if len(token) > 2]
    return " ".join(tokens)


def record_id_from_row(row):
    doi = normalize_doi(row.get("DOI"))
    if doi:
        return f"doi:{doi}"

    title_key = title_fingerprint(row.get("Title"))
    if title_key:
        digest = hashlib.md5(title_key.encode("utf-8")).hexdigest()[:16]
        return f"title:{digest}"

    url = clean_text(row.get("URL")).lower()
    if url:
        digest = hashlib.md5(url.encode("utf-8")).hexdigest()[:16]
        return f"url:{digest}"

    fallback = clean_text(row.get("Title")) + "|" + clean_text(row.get("Authors"))
    digest = hashlib.md5(fallback.encode("utf-8")).hexdigest()[:16]
    return f"row:{digest}"


def to_bibtex_entry(row):
    title = clean_text(row.get("Title", "No title"))
    year = str(row.get("Year", "n.d."))
    authors = clean_text(row.get("Authors", ""))
    doi = clean_text(row.get("DOI"))
    url = clean_text(row.get("URL"))

    first_author = authors.split(",")[0].split(" ")[-1] if authors else "Unknown"
    first_author = re.sub(r"\W+", "", first_author)
    citekey = f"{first_author}{year}"

    bib = f"@article{{{citekey},\n"
    bib += f"  title = {{{title}}},\n"
    if authors:
        bib += f"  author = {{{authors}}},\n"
    bib += f"  year = {{{year}}},\n"
    if doi:
        bib += f"  doi = {{{doi}}},\n"
    if url:
        bib += f"  url = {{{url}}},\n"
    bib += "}\n"
    return bib


def load_persisted_state():
    default_state = {"saved_searches": [], "bookmarks": {}}
    if not os.path.exists(STATE_FILE):
        return default_state

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as handle:
            loaded = json.load(handle)
    except Exception:
        return default_state

    saved_searches = loaded.get("saved_searches", [])
    bookmarks = loaded.get("bookmarks", {})
    if not isinstance(saved_searches, list):
        saved_searches = []
    if not isinstance(bookmarks, dict):
        bookmarks = {}
    return {"saved_searches": saved_searches, "bookmarks": bookmarks}


def persist_state(saved_searches, bookmarks):
    safe_bookmarks = {}
    for key, value in bookmarks.items():
        if not isinstance(value, dict):
            continue
        safe_row = {}
        for row_key, row_value in value.items():
            if isinstance(row_value, (str, int, float, bool)) or row_value is None:
                safe_row[row_key] = row_value
            else:
                safe_row[row_key] = str(row_value)
        safe_bookmarks[str(key)] = safe_row

    payload = {"saved_searches": saved_searches, "bookmarks": safe_bookmarks}
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=True, indent=2)
    except Exception:
        pass


def jaccard_similarity(left_tokens, right_tokens):
    union = left_tokens | right_tokens
    if not union:
        return 0.0
    return len(left_tokens & right_tokens) / len(union)


def merge_result_rows(current, incoming):
    for field in ["Title", "Authors", "Venue", "URL", "PDF", "DOI"]:
        if not clean_text(current.get(field)) and clean_text(incoming.get(field)):
            current[field] = incoming.get(field)

    current["Cites"] = max(normalize_int(current.get("Cites")), normalize_int(incoming.get("Cites")))

    current_year = normalize_year(current.get("Year"))
    incoming_year = normalize_year(incoming.get("Year"))
    if current_year is None:
        current["Year"] = incoming_year
    elif incoming_year is not None:
        current["Year"] = max(current_year, incoming_year)

    current["OA"] = bool(current.get("OA")) or bool(incoming.get("OA"))

    current_abs = clean_text(current.get("Abstract"))
    incoming_abs = clean_text(incoming.get("Abstract"))
    if len(incoming_abs) > len(current_abs):
        current["Abstract"] = incoming_abs

    source_set = {clean_text(item) for item in clean_text(current.get("Source")).split("|") if clean_text(item)}
    source_set.update({clean_text(item) for item in clean_text(incoming.get("Source")).split("|") if clean_text(item)})
    if source_set:
        current["Source"] = " | ".join(sorted(source_set))
        current["SourceCount"] = len(source_set)
    else:
        current["Source"] = clean_text(current.get("Source")) or "Unknown"
        current["SourceCount"] = 1


def compute_relevance_score(query, row, weights=None):
    tokens = [token for token in re.findall(r"[a-z0-9]+", query.lower()) if len(token) > 2]
    searchable_text = f"{clean_text(row.get('Title'))} {clean_text(row.get('Abstract'))}".lower()

    if tokens:
        overlap = sum(1 for token in tokens if token in searchable_text)
        token_score = overlap / len(tokens)
    else:
        token_score = 0.0

    cites = normalize_int(row.get("Cites"))
    citation_score = min(math.log10(cites + 1) / 3.0, 1.0)

    year = normalize_year(row.get("Year"))
    if year is None:
        recency_score = 0.3
    else:
        recency_score = max(0.0, 1.0 - ((CURRENT_YEAR - year) / 20.0))

    if weights is None:
        weights = (0.55, 0.25, 0.20)
    text_weight, citation_weight, recency_weight = weights
    total_weight = text_weight + citation_weight + recency_weight
    if total_weight <= 0:
        text_weight, citation_weight, recency_weight = (0.55, 0.25, 0.20)
    else:
        text_weight /= total_weight
        citation_weight /= total_weight
        recency_weight /= total_weight

    oa_bonus = 0.08 if bool(row.get("OA")) else 0.0
    return (
        (token_score * text_weight)
        + (citation_score * citation_weight)
        + (recency_score * recency_weight)
        + oa_bonus
    )


def deduplicate_results(results, fuzzy_title=False, fuzzy_threshold=0.90):
    merged = {}
    for index, row in enumerate(results):
        doi = normalize_doi(row.get("DOI"))
        title_key = title_fingerprint(row.get("Title"))
        key = doi or title_key or f"row-{index}"

        if key not in merged:
            item = dict(row)
            source = clean_text(item.get("Source"))
            item["_source_set"] = {source} if source else set()
            item["Cites"] = normalize_int(item.get("Cites"))
            item["Year"] = normalize_year(item.get("Year"))
            item["OA"] = bool(item.get("OA"))
            merged[key] = item
            continue

        current = merged[key]
        source = clean_text(row.get("Source"))
        if source:
            current["_source_set"].add(source)

        merge_result_rows(current, row)

    output = []
    for item in merged.values():
        sources = sorted(item.pop("_source_set", []))
        if sources:
            item["Source"] = " | ".join(sources)
            item["SourceCount"] = len(sources)
        else:
            item["Source"] = clean_text(item.get("Source")) or "Unknown"
            item["SourceCount"] = 1
        output.append(item)

    if not fuzzy_title:
        return output

    refined = []
    for row in output:
        row_copy = dict(row)
        row_tokens = set(title_fingerprint(row_copy.get("Title")).split())
        row_doi = normalize_doi(row_copy.get("DOI"))
        merged_into_existing = False

        for existing in refined:
            existing_doi = normalize_doi(existing.get("DOI"))
            should_merge = False

            if row_doi and existing_doi and row_doi == existing_doi:
                should_merge = True
            elif not row_doi and not existing_doi:
                existing_tokens = set(title_fingerprint(existing.get("Title")).split())
                similarity = jaccard_similarity(row_tokens, existing_tokens)
                if similarity >= fuzzy_threshold:
                    should_merge = True

            if should_merge:
                merge_result_rows(existing, row_copy)
                merged_into_existing = True
                break

        if not merged_into_existing:
            refined.append(row_copy)

    return refined


def extract_top_keywords(series, top_n=12):
    counter = Counter()
    for value in series.fillna("").astype(str):
        for token in re.findall(r"[a-zA-Z]{3,}", value.lower()):
            if token in STOPWORDS:
                continue
            counter[token] += 1
    return counter.most_common(top_n)


def build_author_counts(df, top_n=10):
    counter = Counter()
    for raw_value in df["Authors"].fillna("").astype(str):
        parts = re.split(r",|;", raw_value)
        for part in parts:
            name = clean_text(part)
            if name:
                counter[name] += 1
    rows = [{"Author": name, "Count": count} for name, count in counter.most_common(top_n)]
    return pd.DataFrame(rows)


def build_source_counts(df):
    counter = Counter()
    for raw_value in df["Source"].fillna("").astype(str):
        parts = [clean_text(part) for part in raw_value.split("|")]
        for part in parts:
            if part:
                counter[part] += 1
    rows = [{"Source": source, "Count": count} for source, count in counter.most_common()]
    return pd.DataFrame(rows)


def build_research_brief(df, query):
    if df.empty:
        return "No dataset summary is available yet."

    source_counts = build_source_counts(df)
    top_source = source_counts.iloc[0]["Source"] if not source_counts.empty else "N/A"

    venue_counts = (
        df[df["Venue"].notna() & (df["Venue"] != "")]
        .groupby("Venue")
        .size()
        .sort_values(ascending=False)
    )
    top_venue = venue_counts.index[0] if not venue_counts.empty else "N/A"

    keyword_list = [item[0] for item in extract_top_keywords(df["Title"], top_n=5)]
    keyword_text = ", ".join(keyword_list) if keyword_list else "none"

    oa_ratio = (df["OA"].mean() * 100.0) if not df.empty else 0.0
    med_cites = int(df["Cites"].median()) if not df.empty else 0

    return (
        f"Query '{query}' returned {len(df)} filtered papers. "
        f"Most represented source: {top_source}. "
        f"Top venue: {top_venue}. "
        f"Median citations: {med_cites}. "
        f"Open-access share: {oa_ratio:.1f}%. "
        f"Recurring title keywords: {keyword_text}."
    )


def build_markdown_brief(df, query, source_stats=None, top_n=10):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        f"# Research Brief: {query}",
        "",
        f"Generated: {now}",
        "",
        "## Summary",
        f"- Filtered papers: {len(df)}",
        f"- Open-access ratio: {df['OA'].mean() * 100:.1f}%",
        f"- Median citations: {int(df['Cites'].median()) if not df.empty else 0}",
        "",
    ]

    if source_stats:
        lines.append("## Source Diagnostics")
        for stat in source_stats:
            status = "ok" if not stat.get("error") else "error"
            lines.append(
                f"- {stat.get('source')}: {stat.get('result_count', 0)} results, "
                f"{stat.get('duration_sec', 0.0):.2f}s, status={status}"
            )
        lines.append("")

    lines.append("## Top Papers")
    top_df = df.head(top_n)
    for _, row in top_df.iterrows():
        lines.append(
            f"- **{row['Title']}** ({row['Year']}) | Score={row['Score']:.3f} | "
            f"Cites={row['Cites']} | Source={row['Source']}"
        )
        if clean_text(row.get("URL")):
            lines.append(f"  - Link: {row['URL']}")
    lines.append("")

    lines.append("## Notes")
    lines.append("- Ranking combines text relevance, citation signal, recency, and open-access bonus.")
    lines.append("- Dedupe merges repeated entries across sources by DOI/title.")
    lines.append("")
    return "\n".join(lines)


def prepare_dataframe(results, query, score_weights=None):
    if not results:
        return pd.DataFrame()

    df = pd.DataFrame(results)
    expected_columns = [
        "Source",
        "Title",
        "Authors",
        "Year",
        "Venue",
        "URL",
        "PDF",
        "DOI",
        "Cites",
        "Abstract",
        "OA",
        "SourceCount",
    ]
    for column in expected_columns:
        if column not in df.columns:
            df[column] = None

    df["Title"] = df["Title"].fillna("Untitled").apply(clean_text)
    df["Authors"] = df["Authors"].fillna("Unknown").apply(clean_text)
    df["Venue"] = df["Venue"].fillna("").apply(clean_text)
    df["URL"] = df["URL"].fillna("").apply(clean_text)
    df["PDF"] = df["PDF"].fillna("").apply(clean_text)
    df["DOI"] = df["DOI"].fillna("").apply(clean_text)
    df["Abstract"] = df["Abstract"].fillna("").apply(clean_text)
    df["Source"] = df["Source"].fillna("Unknown").apply(clean_text)

    df["Year"] = df["Year"].apply(normalize_year)
    df["Cites"] = df["Cites"].apply(normalize_int)
    df["OA"] = df["OA"].apply(lambda value: bool(value))
    df["SourceCount"] = df["SourceCount"].fillna(1).apply(normalize_int).clip(lower=1)

    df["RecordId"] = df.apply(record_id_from_row, axis=1)
    df["Score"] = df.apply(
        lambda row: round(compute_relevance_score(query, row, weights=score_weights), 4),
        axis=1,
    )
    return df
