import itertools
import unittest

from src.app_utils import (
    CURRENT_YEAR, build_markdown_brief, compute_relevance_score, deduplicate_results,
    normalize_doi, prepare_dataframe, prepare_results, record_id_from_row, to_bibtex_entry,
)


def paper(**overrides):
    return {"Source": "OpenAlex", "Title": "Graph neural networks", "Authors": "Alice Smith, Bob Jones",
            "Year": 2025, "Venue": "Test Journal", "URL": "https://example.org/paper", "PDF": "",
            "DOI": "10.1234/example", "Cites": 5, "Abstract": "Learning on graphs", "OA": False,
            "OAStatus": "unknown", **overrides}


class ResultTests(unittest.TestCase):
    def test_doi_normalization(self):
        for value in [None, "None", "NaN", "null", "not-a-doi", ""]:
            self.assertEqual(normalize_doi(value), "")
        self.assertEqual(normalize_doi("DOI: 10.1234/ABC"), "10.1234/abc")
        self.assertEqual(normalize_doi("https://dx.doi.org/10.1234/ABC"), "10.1234/abc")

    def test_missing_doi_does_not_merge_unrelated_titles(self):
        rows = deduplicate_results([paper(DOI="None"), paper(DOI="None", Title="Other research")])
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(row["DOI"] == "" for row in rows))

    def test_title_only_and_doi_record_merge_in_either_order(self):
        for rows in itertools.permutations([paper(), paper(DOI="", Source="ArXiv")]):
            for fuzzy in [False, True]:
                result = deduplicate_results(rows, fuzzy_title=fuzzy)
                self.assertEqual(len(result), 1)
                self.assertEqual(result[0]["DOI"], "10.1234/example")
                self.assertEqual(result[0]["SourceCount"], 2)

    def test_different_dois_are_never_bridged_by_title_only_record(self):
        inputs = [paper(), paper(DOI="10.1234/different"), paper(DOI="", Source="ArXiv")]
        for rows in itertools.permutations(inputs):
            self.assertEqual(len(deduplicate_results(rows, fuzzy_title=True)), 3)

    def test_same_title_different_authors_or_years_stay_separate(self):
        for other in [paper(DOI="", Authors="Carol Brown"), paper(DOI="", Year=2020)]:
            self.assertEqual(len(deduplicate_results([paper(), other], fuzzy_title=True)), 2)

    def test_same_doi_merges_sources_and_retains_first_known_year(self):
        rows = deduplicate_results([paper(), paper(Source="Crossref", Year=2024, Cites=9)])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["SourceCount"], 2)
        self.assertEqual(rows[0]["Cites"], 9)
        self.assertEqual(rows[0]["Year"], 2025)

    def test_untitled_records_do_not_merge_by_placeholder(self):
        rows = [paper(DOI="", Title="Untitled", URL="https://example.org/1"),
                paper(DOI="", Title="Untitled", URL="https://example.org/2")]
        self.assertEqual(len(deduplicate_results(rows, fuzzy_title=True)), 2)
        self.assertNotEqual(record_id_from_row(rows[0]), record_id_from_row(rows[1]))

    def test_unicode_titles_do_not_collapse_to_ascii(self):
        rows = [paper(DOI="", Title="Öğrenme yöntemleri"), paper(DOI="", Title="Ölçüm yöntemleri")]
        self.assertEqual(len(deduplicate_results(rows)), 2)

    def test_word_boundaries_in_relevance(self):
        row = paper(Title="Education methods", Abstract="", OA=False)
        self.assertEqual(compute_relevance_score("cat", row, (1, 0, 0)), 0)
        self.assertEqual(compute_relevance_score("education", row, (1, 0, 0)), 1)

    def test_unicode_and_short_acronyms_match(self):
        self.assertEqual(compute_relevance_score("AI öğrenme", paper(Title="AI öğrenme", Abstract=""), (1, 0, 0)), 1)
        self.assertEqual(compute_relevance_score("iha", paper(Title="İHA", Abstract=""), (1, 0, 0)), 1)

    def test_future_year_recency_is_bounded(self):
        self.assertEqual(compute_relevance_score("absent", paper(Year=CURRENT_YEAR + 10), (0, 0, 1)), 1)

    def test_missing_years_serialize_as_nullable_integers(self):
        df = prepare_dataframe([paper(Year=None), paper(Year=2025)], "graph")
        self.assertEqual(str(df["Year"].dtype), "Int64")
        self.assertEqual(df["Year"].isna().sum(), 1)
        self.assertIn("TextMatch", df)

    def test_preparation_ranks_by_same_shared_rules(self):
        _, df = prepare_results([paper(Title="Other topic", Abstract="", DOI="10.1234/other"), paper()], "graph neural networks")
        self.assertEqual(df.iloc[0]["Title"], "Graph neural networks")

    def test_bibtex_keys_are_unique_and_authors_are_separated(self):
        first = to_bibtex_entry(paper())
        second = to_bibtex_entry(paper(DOI="10.1234/other", Title="Other paper"))
        self.assertNotEqual(first.splitlines()[0], second.splitlines()[0])
        self.assertIn("Alice Smith and Bob Jones", first)
        self.assertIn("year = {2025}", first)
        self.assertNotIn("2025.0", first)

    def test_bibtex_escapes_special_characters_and_omits_missing_year(self):
        bib = to_bibtex_entry(paper(Title="A {test} & 50%", Year=None))
        self.assertIn(r"A \{test\} \& 50\%", bib)
        self.assertNotIn("year =", bib)
        self.assertRegex(bib.splitlines()[0], r"^@article\{Smithnd_[a-f0-9]{8},$")

    def test_empty_snapshot_does_not_crash(self):
        df = prepare_dataframe([paper()], "graph").iloc[:0]
        self.assertIn("Open-access ratio: 0.0%", build_markdown_brief(df, "graph"))


if __name__ == "__main__":
    unittest.main()
