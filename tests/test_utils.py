"""
Unit tests for the pure utility functions in src/utils.py.
"""
from src.utils import clean_text, format_authors


# ---------------------------------------------------------------------------
# clean_text
# ---------------------------------------------------------------------------

class TestCleanText:
    def test_none_returns_empty(self):
        assert clean_text(None) == ""

    def test_empty_string_returns_empty(self):
        assert clean_text("") == ""

    def test_collapses_whitespace(self):
        assert clean_text("hello   world") == "hello world"

    def test_strips_newlines(self):
        assert clean_text("line1\nline2") == "line1 line2"

    def test_strips_tabs(self):
        assert clean_text("col1\tcol2") == "col1 col2"

    def test_list_joined(self):
        assert clean_text(["hello", "world"]) == "hello world"

    def test_integer_converted(self):
        assert clean_text(99) == "99"


# ---------------------------------------------------------------------------
# format_authors
# ---------------------------------------------------------------------------

class TestFormatAuthors:
    def test_none_returns_na(self):
        assert format_authors(None) == "N/A"

    def test_empty_list_returns_na(self):
        assert format_authors([]) == "N/A"

    def test_dict_with_name_key(self):
        result = format_authors([{"name": "Alice Smith"}])
        assert "Alice Smith" in result

    def test_dict_with_given_family(self):
        result = format_authors([{"given": "Bob", "family": "Jones"}])
        assert "Bob Jones" in result

    def test_plain_string_list(self):
        result = format_authors(["Alice", "Bob", "Carol"])
        assert "Alice" in result
        assert "Bob" in result

    def test_at_most_three_authors(self):
        authors = [{"name": f"Author{i}"} for i in range(10)]
        result = format_authors(authors)
        assert result.count(";") <= 2  # max 3 authors → at most 2 semicolons

    def test_semicolon_separator(self):
        result = format_authors([{"name": "A"}, {"name": "B"}])
        assert ";" in result
