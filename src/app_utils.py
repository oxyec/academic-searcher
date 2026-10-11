import hashlib
import json
import math
import os
import re
import unicodedata
from collections import Counter
from datetime import datetime

import pandas as pd

CURRENT_YEAR = datetime.now().year
STATE_FILE = ".academic_search_state.json"
PERSIST_STATE_ENV = "ACADEMIC_SEARCH_PERSIST_STATE"
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


def state_persistence_enabled():
    value = os.getenv(PERSIST_STATE_ENV, "false")
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


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
    doi = clean_text(value).casefold()
    doi = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", doi)
    return doi if re.fullmatch(r"10\.\d{4,9}/\S+", doi) else ""


def text_tokens(value):
    text = unicodedata.normalize("NFC", clean_text(value)).casefold().replace("\u0307", "")
    return re.findall(r"[^\W_]+", text, flags=re.UNICODE)


def title_fingerprint(title):
    return " ".join(text_tokens(title))


def record_id_from_row(row):
    doi = normalize_doi(row.get("DOI"))
    if doi:
        return f"doi:{doi}"

    title_key = title_fingerprint(row.get("Title"))
    if title_key and title_key not in {"untitled", "no title"}:
        identity = f"{title_key}|{normalize_year(row.get('Year'))}|{clean_text(row.get('Authors')).casefold()}"
        digest = hashlib.md5(identity.encode("utf-8")).hexdigest()[:16]
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
    year = normalize_year(row.get("Year"))
    authors = clean_text(row.get("Authors", ""))
    doi = normalize_doi(row.get("DOI"))
    url = clean_text(row.get("URL"))

    first_author = re.split(r",|;", authors)[0].split(" ")[-1] if authors else "Unknown"
    first_author = re.sub(r"\W+", "", first_author)
    digest = hashlib.md5(record_id_from_row(row).encode("utf-8")).hexdigest()[:8]
    citekey = f"{first_author or 'Unknown'}{year or 'nd'}_{digest}"

    def escape(value):
        replacements = {
            "\\": r"\textbackslash{}", "{": r"\{", "}": r"\}", "&": r"\&", "%": r"\%",
            "_": r"\_", "#": r"\#", "$": r"\$", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
        }
        return "".join(replacements.get(char, char) for char in value)

    bib = f"@article{{{citekey},\n"
    bib += f"  title = {{{escape(title)}}},\n"
    if authors:
        names = [name.strip() for name in re.split(r",|;", authors) if name.strip()]
        bib += f"  author = {{{' and '.join(escape(name) for name in names)}}},\n"
    if year is not None:
        bib += f"  year = {{{year}}},\n"
    venue = clean_text(row.get("Venue"))
    if venue:
        bib += f"  journal = {{{escape(venue)}}},\n"
    if doi:
        bib += f"  doi = {{{escape(doi)}}},\n"
    if url:
        bib += f"  url = {{{escape(url)}}},\n"
    bib += "}\n"
    return bib


def load_persisted_state():
    default_state = {"saved_searches": [], "bookmarks": {}}
    if not state_persistence_enabled():
        return default_state
    if not os.path.exists(STATE_FILE):
        return default_state

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as handle:
            loaded = json.load(handle)
    except Exception:
        return default_state

    if not isinstance(loaded, dict):
        return default_state

    saved_searches = loaded.get("saved_searches", [])
    bookmarks = loaded.get("bookmarks", {})
    if not isinstance(saved_searches, list):
        saved_searches = []
    if not isinstance(bookmarks, dict):
        bookmarks = {}
    return {"saved_searches": saved_searches, "bookmarks": bookmarks}


def persist_state(saved_searches, bookmarks):
    if not state_persistence_enabled():
        return

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

    current["OA"] = bool(current.get("OA")) or bool(incoming.get("OA"))
    if current.get("OAStatus", "unknown") == "unknown" or bool(incoming.get("OA")):
        current["OAStatus"] = incoming.get("OAStatus", "unknown")

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


def compute_score_details(query, row, weights=None):
    tokens = {token for token in text_tokens(query) if len(token) > 1}
    searchable_tokens = set(text_tokens(f"{clean_text(row.get('Title'))} {clean_text(row.get('Abstract'))}"))

    if tokens:
        token_score = len(tokens & searchable_tokens) / len(tokens)
    else:
        token_score = 0.0

    cites = max(0, normalize_int(row.get("Cites")))
    citation_score = min(math.log10(cites + 1) / 3.0, 1.0)

    year = normalize_year(row.get("Year"))
    if year is None:
        recency_score = 0.3
    else:
        recency_score = min(1.0, max(0.0, 1.0 - ((CURRENT_YEAR - year) / 20.0)))

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
    score = (
        (token_score * text_weight)
        + (citation_score * citation_weight)
        + (recency_score * recency_weight)
        + oa_bonus
    )
    return {
        "Score": round(score, 4), "TextMatch": round(token_score, 4),
        "CitationSignal": round(citation_score, 4), "RecencySignal": round(recency_score, 4),
        "OpenAccessBonus": oa_bonus,
    }


def compute_relevance_score(query, row, weights=None):
    return compute_score_details(query, row, weights)["Score"]


def _compatible_title_rows(left, right):
    left_year, right_year = normalize_year(left.get("Year")), normalize_year(right.get("Year"))
    if left_year is not None and right_year is not None and left_year != right_year:
        return False
    left_authors = {title_fingerprint(name) for name in re.split(r",|;", clean_text(left.get("Authors"))) if name.strip()}
    right_authors = {title_fingerprint(name) for name in re.split(r",|;", clean_text(right.get("Authors"))) if name.strip()}
    placeholders = {"unknown", "n a", "see link"}
    left_authors -= placeholders
    right_authors -= placeholders
    return not left_authors or not right_authors or bool(left_authors & right_authors)


def deduplicate_results(results, fuzzy_title=False, fuzzy_threshold=0.90):
    # Resolve DOI identities first, so title-only records cannot bridge conflicting DOIs.
    output = []
    doi_rows = {}
    for row in results:
        doi = normalize_doi(row.get("DOI"))
        if doi and doi in doi_rows:
            merge_result_rows(doi_rows[doi], row)
            continue
        item = dict(row)
        item["DOI"] = doi
        item["Cites"] = max(0, normalize_int(item.get("Cites")))
        item["Year"] = normalize_year(item.get("Year"))
        item["OA"] = bool(item.get("OA"))
        sources = sorted({part.strip() for part in clean_text(item.get("Source")).split("|") if part.strip()})
        item["Source"] = " | ".join(sources) or "Unknown"
        item["SourceCount"] = len(sources) or 1
        output.append(item)
        if doi:
            doi_rows[doi] = item

    by_title = {}
    for item in output:
        title = title_fingerprint(item.get("Title"))
        if title and title not in {"untitled", "no title"} and item["DOI"]:
            by_title.setdefault(title, []).append(item)
    removed = set()
    for item in output:
        if item["DOI"]:
            continue
        title = title_fingerprint(item.get("Title"))
        if not title or title in {"untitled", "no title"}:
            continue
        candidates = by_title.get(title, [])
        compatible = [other for other in candidates if _compatible_title_rows(item, other)]
        if len(candidates) == 1 and len(compatible) == 1:
            merge_result_rows(compatible[0], item)
            removed.add(id(item))
        else:
            by_title.setdefault(title, []).append(item)
    output = [item for item in output if id(item) not in removed]

    if not fuzzy_title:
        return output

    refined = []
    for row in output:
        row_copy = dict(row)
        row_title = title_fingerprint(row_copy.get("Title"))
        row_tokens = set(row_title.split())
        row_doi = normalize_doi(row_copy.get("DOI"))
        merged_into_existing = False

        for existing in refined:
            existing_doi = normalize_doi(existing.get("DOI"))
            existing_title = title_fingerprint(existing.get("Title"))
            should_merge = False

            if row_doi and existing_doi and row_doi == existing_doi:
                should_merge = True
            elif (not row_doi and not existing_doi and row_tokens
                  and row_title not in {"untitled", "no title"}
                  and existing_title not in {"untitled", "no title"}
                  and _compatible_title_rows(row_copy, existing)):
                existing_tokens = set(existing_title.split())
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
        for token in text_tokens(value):
            if len(token) < 3 or token in STOPWORDS:
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
        f"# Search Snapshot: {query}",
        "",
        f"Generated: {now}",
        "",
        "## Summary",
        f"- Filtered papers: {len(df)}",
        f"- Open-access ratio: {df['OA'].mean() * 100 if not df.empty else 0:.1f}%",
        f"- Median citations: {int(df['Cites'].median()) if not df.empty else 0}",
        "",
    ]

    if source_stats:
        lines.append("## Source Diagnostics")
        for stat in source_stats:
            status = stat.get("status", "Error" if stat.get("error") else "OK").lower()
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
    lines.append("- This is a summary of retrieved metadata, not a synthesis of paper findings or an exhaustive literature review.")
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
    df["DOI"] = df["DOI"].fillna("").apply(normalize_doi)
    df["Abstract"] = df["Abstract"].fillna("").apply(clean_text)
    df["Source"] = df["Source"].fillna("Unknown").apply(clean_text)

    df["Year"] = df["Year"].apply(normalize_year).astype("Int64")
    df["Cites"] = df["Cites"].apply(normalize_int).clip(lower=0)
    df["OA"] = df["OA"].fillna(False).astype(bool)
    df["SourceCount"] = df["SourceCount"].apply(normalize_int).clip(lower=1)

    df["RecordId"] = df.apply(record_id_from_row, axis=1)
    scores = pd.DataFrame([compute_score_details(query, row, weights=score_weights) for _, row in df.iterrows()], index=df.index)
    for column in scores:
        df[column] = scores[column]
    return df


def prepare_results(results, query, dedupe=True, fuzzy_title=False, fuzzy_threshold=0.90, score_weights=None):
    rows = deduplicate_results(results, fuzzy_title, fuzzy_threshold) if dedupe else results
    df = prepare_dataframe(rows, query, score_weights=score_weights)
    if not df.empty:
        df = df.sort_values(["Score", "Cites", "RecordId"], ascending=[False, False, True], kind="mergesort")
    return rows, df
