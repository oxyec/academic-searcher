"""
Unit tests for the pure utility functions in src/app_utils.py.
"""
import pytest
from src.app_utils import (
    clean_text,
    normalize_doi,
    normalize_int,
    normalize_year,
    title_fingerprint,
    jaccard_similarity,
    record_id_from_row,
    to_bibtex_entry,
    merge_result_rows,
    compute_relevance_score,
    deduplicate_results,
    extract_top_keywords,
    state_persistence_enabled,
)
import pandas as pd


# ---------------------------------------------------------------------------
# clean_text
# ---------------------------------------------------------------------------

class TestCleanText:
    def test_none_returns_empty_string(self):
        assert clean_text(None) == ""

    def test_collapses_internal_whitespace(self):
        assert clean_text("hello   world") == "hello world"

    def test_strips_leading_trailing_whitespace(self):
        assert clean_text("  hello  ") == "hello"

    def test_integer_converted_to_string(self):
        assert clean_text(42) == "42"

    def test_newlines_collapsed(self):
        assert clean_text("line1\nline2") == "line1 line2"


# ---------------------------------------------------------------------------
# normalize_doi
# ---------------------------------------------------------------------------

class TestNormalizeDoi:
    def test_strips_https_prefix(self):
        assert normalize_doi("https://doi.org/10.1000/xyz") == "10.1000/xyz"

    def test_strips_http_prefix(self):
        assert normalize_doi("http://doi.org/10.1000/xyz") == "10.1000/xyz"

    def test_lowercases(self):
        assert normalize_doi("10.1000/XYZ") == "10.1000/xyz"

    def test_empty_string_returns_empty(self):
        assert normalize_doi("") == ""

    def test_none_returns_empty(self):
        assert normalize_doi(None) == ""


# ---------------------------------------------------------------------------
# normalize_int
# ---------------------------------------------------------------------------

class TestNormalizeInt:
    def test_integer_passthrough(self):
        assert normalize_int(5) == 5

    def test_float_truncated(self):
        assert normalize_int(3.9) == 3

    def test_string_number(self):
        assert normalize_int("10") == 10

    def test_none_returns_zero(self):
        assert normalize_int(None) == 0

    def test_empty_string_returns_zero(self):
        assert normalize_int("") == 0

    def test_invalid_string_returns_zero(self):
        assert normalize_int("abc") == 0


# ---------------------------------------------------------------------------
# normalize_year
# ---------------------------------------------------------------------------

class TestNormalizeYear:
    def test_integer_passthrough(self):
        assert normalize_year(2023) == 2023

    def test_string_number(self):
        assert normalize_year("2020") == 2020

    def test_none_returns_none(self):
        assert normalize_year(None) is None

    def test_empty_string_returns_none(self):
        assert normalize_year("") is None

    def test_invalid_string_returns_none(self):
        assert normalize_year("abc") is None


# ---------------------------------------------------------------------------
# title_fingerprint
# ---------------------------------------------------------------------------

class TestTitleFingerprint:
    def test_lowercases_and_strips_punctuation(self):
        fp = title_fingerprint("Hello, World!")
        assert "," not in fp
        assert "!" not in fp

    def test_removes_short_tokens(self):
        fp = title_fingerprint("A B Deep Learning")
        assert " a " not in fp.split()
        assert " b " not in fp.split()
        assert "deep" in fp
        assert "learning" in fp

    def test_empty_string(self):
        assert title_fingerprint("") == ""

    def test_none_input(self):
        assert title_fingerprint(None) == ""


# ---------------------------------------------------------------------------
# jaccard_similarity
# ---------------------------------------------------------------------------

class TestJaccardSimilarity:
    def test_identical_sets(self):
        tokens = {"deep", "learning", "neural"}
        assert jaccard_similarity(tokens, tokens) == 1.0

    def test_disjoint_sets(self):
        assert jaccard_similarity({"a", "b"}, {"c", "d"}) == 0.0

    def test_partial_overlap(self):
        left = {"a", "b", "c"}
        right = {"b", "c", "d"}
        # intersection=2, union=4
        assert jaccard_similarity(left, right) == pytest.approx(0.5)

    def test_empty_sets(self):
        assert jaccard_similarity(set(), set()) == 0.0


# ---------------------------------------------------------------------------
# record_id_from_row
# ---------------------------------------------------------------------------

class TestRecordIdFromRow:
    def test_prefers_doi(self):
        row = {"DOI": "10.1000/xyz", "Title": "Some Title", "URL": ""}
        rid = record_id_from_row(row)
        assert rid.startswith("doi:")

    def test_falls_back_to_title(self):
        row = {"DOI": "", "Title": "A Long Enough Title", "Authors": "", "URL": ""}
        rid = record_id_from_row(row)
        assert rid.startswith("title:")

    def test_falls_back_to_url(self):
        row = {"DOI": "", "Title": "", "Authors": "", "URL": "https://example.com/paper"}
        rid = record_id_from_row(row)
        assert rid.startswith("url:")

    def test_fallback_row_hash(self):
        row = {"DOI": "", "Title": "", "Authors": "", "URL": ""}
        rid = record_id_from_row(row)
        assert rid.startswith("row:")


# ---------------------------------------------------------------------------
# to_bibtex_entry
# ---------------------------------------------------------------------------

class TestToBibtexEntry:
    def test_contains_title(self):
        row = {"Title": "My Paper", "Year": 2022, "Authors": "Smith, John", "DOI": "", "URL": ""}
        bib = to_bibtex_entry(row)
        assert "My Paper" in bib

    def test_contains_year(self):
        row = {"Title": "My Paper", "Year": 2022, "Authors": "Smith, John", "DOI": "", "URL": ""}
        bib = to_bibtex_entry(row)
        assert "2022" in bib

    def test_doi_included_when_present(self):
        row = {"Title": "My Paper", "Year": 2022, "Authors": "Smith, John", "DOI": "10.1/x", "URL": ""}
        bib = to_bibtex_entry(row)
        assert "doi" in bib

    def test_doi_omitted_when_absent(self):
        row = {"Title": "My Paper", "Year": 2022, "Authors": "Smith, John", "DOI": "", "URL": ""}
        bib = to_bibtex_entry(row)
        assert "doi" not in bib

    def test_article_type(self):
        row = {"Title": "X", "Year": 2020, "Authors": "", "DOI": "", "URL": ""}
        assert to_bibtex_entry(row).startswith("@article")


# ---------------------------------------------------------------------------
# merge_result_rows
# ---------------------------------------------------------------------------

class TestMergeResultRows:
    def test_fills_missing_title(self):
        current = {"Title": "", "Authors": "", "Venue": "", "URL": "", "PDF": "", "DOI": "",
                   "Cites": 0, "Year": None, "OA": False, "Abstract": "", "Source": "A"}
        incoming = {"Title": "Found Title", "Authors": "", "Venue": "", "URL": "", "PDF": "", "DOI": "",
                    "Cites": 0, "Year": None, "OA": False, "Abstract": "", "Source": "B"}
        merge_result_rows(current, incoming)
        assert current["Title"] == "Found Title"

    def test_keeps_max_cites(self):
        current = {"Title": "T", "Authors": "", "Venue": "", "URL": "", "PDF": "", "DOI": "",
                   "Cites": 10, "Year": 2020, "OA": False, "Abstract": "", "Source": "A"}
        incoming = {"Title": "T", "Authors": "", "Venue": "", "URL": "", "PDF": "", "DOI": "",
                    "Cites": 50, "Year": 2020, "OA": False, "Abstract": "", "Source": "B"}
        merge_result_rows(current, incoming)
        assert current["Cites"] == 50

    def test_oa_flag_becomes_true_if_either_is_true(self):
        current = {"Title": "T", "Authors": "", "Venue": "", "URL": "", "PDF": "", "DOI": "",
                   "Cites": 0, "Year": 2020, "OA": False, "Abstract": "", "Source": "A"}
        incoming = {"Title": "T", "Authors": "", "Venue": "", "URL": "", "PDF": "", "DOI": "",
                    "Cites": 0, "Year": 2020, "OA": True, "Abstract": "", "Source": "B"}
        merge_result_rows(current, incoming)
        assert current["OA"] is True


# ---------------------------------------------------------------------------
# compute_relevance_score
# ---------------------------------------------------------------------------

class TestComputeRelevanceScore:
    def _row(self, title="", abstract="", cites=0, year=2020, oa=False):
        return {"Title": title, "Abstract": abstract, "Cites": cites, "Year": year, "OA": oa}

    def test_score_is_float_between_zero_and_one_plus_oa_bonus(self):
        row = self._row(title="deep learning neural networks", cites=100, year=2022, oa=True)
        score = compute_relevance_score("deep learning", row)
        assert 0.0 <= score <= 1.1  # max 1.0 + 0.08 OA bonus

    def test_exact_title_match_scores_higher_than_unrelated(self):
        relevant = self._row(title="deep learning for image recognition", cites=10, year=2022)
        irrelevant = self._row(title="history of ancient rome", cites=10, year=2022)
        s1 = compute_relevance_score("deep learning", relevant)
        s2 = compute_relevance_score("deep learning", irrelevant)
        assert s1 > s2

    def test_oa_bonus_applied(self):
        base = self._row(title="same title", cites=0, year=2020, oa=False)
        oa = self._row(title="same title", cites=0, year=2020, oa=True)
        assert compute_relevance_score("same title", oa) > compute_relevance_score("same title", base)

    def test_custom_weights_normalised(self):
        row = self._row(title="machine learning", cites=5, year=2021)
        # Should not raise and should return a valid score
        score = compute_relevance_score("machine learning", row, weights=(1.0, 0.0, 0.0))
        assert isinstance(score, float)


# ---------------------------------------------------------------------------
# deduplicate_results
# ---------------------------------------------------------------------------

class TestDeduplicateResults:
    def _make(self, title, doi="", source="S1", cites=0):
        return {"Title": title, "DOI": doi, "Source": source, "Cites": cites,
                "Year": 2020, "OA": False, "Abstract": "", "URL": "", "Authors": "", "Venue": "", "PDF": ""}

    def test_exact_doi_duplicates_removed(self):
        rows = [
            self._make("Paper A", doi="10.1/x", source="S1"),
            self._make("Paper A (variant)", doi="10.1/x", source="S2"),
        ]
        result = deduplicate_results(rows)
        assert len(result) == 1

    def test_exact_title_duplicates_removed(self):
        rows = [
            self._make("Deep Learning Survey", source="S1"),
            self._make("Deep Learning Survey", source="S2"),
        ]
        result = deduplicate_results(rows)
        assert len(result) == 1

    def test_distinct_papers_preserved(self):
        rows = [
            self._make("Paper Alpha"),
            self._make("Paper Beta"),
        ]
        result = deduplicate_results(rows)
        assert len(result) == 2

    def test_merged_source_count(self):
        rows = [
            self._make("Paper A", doi="10.1/x", source="S1"),
            self._make("Paper A", doi="10.1/x", source="S2"),
        ]
        result = deduplicate_results(rows)
        assert result[0]["SourceCount"] == 2

    def test_fuzzy_title_merge(self):
        rows = [
            self._make("A Survey of Deep Learning Methods"),
            self._make("A Survey of Deep Learning Methods"),  # identical => similarity=1.0
        ]
        result = deduplicate_results(rows, fuzzy_title=True, fuzzy_threshold=0.9)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# extract_top_keywords
# ---------------------------------------------------------------------------

class TestExtractTopKeywords:
    def test_returns_tuples(self):
        series = pd.Series(["deep learning neural network", "deep convolutional neural"])
        keywords = extract_top_keywords(series, top_n=3)
        assert all(isinstance(k, tuple) and len(k) == 2 for k in keywords)

    def test_stopwords_excluded(self):
        series = pd.Series(["this paper using with about"])
        keywords = extract_top_keywords(series, top_n=10)
        words = [w for w, _ in keywords]
        for sw in ("this", "paper", "using", "with", "about"):
            assert sw not in words

    def test_top_n_respected(self):
        series = pd.Series(["word1 word2 word3 word4 word5 word6"])
        keywords = extract_top_keywords(series, top_n=3)
        assert len(keywords) <= 3

    def test_empty_series(self):
        assert extract_top_keywords(pd.Series([], dtype=str), top_n=5) == []


# ---------------------------------------------------------------------------
# state_persistence_enabled
# ---------------------------------------------------------------------------

class TestStatePersistenceEnabled:
    def test_disabled_by_default(self, monkeypatch):
        monkeypatch.delenv("ACADEMIC_SEARCH_PERSIST_STATE", raising=False)
        assert state_persistence_enabled() is False

    def test_enabled_with_true(self, monkeypatch):
        monkeypatch.setenv("ACADEMIC_SEARCH_PERSIST_STATE", "true")
        assert state_persistence_enabled() is True

    def test_enabled_with_1(self, monkeypatch):
        monkeypatch.setenv("ACADEMIC_SEARCH_PERSIST_STATE", "1")
        assert state_persistence_enabled() is True

    def test_disabled_with_false(self, monkeypatch):
        monkeypatch.setenv("ACADEMIC_SEARCH_PERSIST_STATE", "false")
        assert state_persistence_enabled() is False
