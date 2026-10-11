import contextlib
import csv
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import main
from src import export


class CliTests(unittest.IsolatedAsyncioTestCase):
    def test_csv_export_preserves_research_metadata(self):
        with tempfile.TemporaryDirectory(prefix="academic-export-") as directory:
            output = Path(directory) / "results.csv"
            with patch.object(export, "OUTPUT_CSV", str(output)):
                export.save_to_csv({"title": "Öğrenme", "year": 2025, "citations": 7,
                                    "abstract": "Useful abstract", "score": 0.8, "source_count": 2})
            with output.open(encoding="utf-8-sig", newline="") as handle:
                row = next(csv.DictReader(handle))
            self.assertEqual(row["Title"], "Öğrenme")
            self.assertEqual(row["Citations"], "7")
            self.assertEqual(row["Abstract"], "Useful abstract")
            self.assertEqual(row["Relevance Score"], "0.8")
            self.assertEqual(row["Source Count"], "2")

    async def test_partial_failure_exports_available_results_and_reports_failure(self):
        row = {"title": "Available", "year": 2025}
        stats = [{"source": "OpenAlex", "status": "Error", "error": "HTTP 429"},
                 {"source": "ArXiv", "status": "OK", "error": ""}]
        output = io.StringIO()
        with patch("builtins.input", side_effect=["graph", "q"]), \
             patch.object(main, "search_with_diagnostics_async", AsyncMock(return_value=([row], stats))), \
             patch.object(main, "save_to_csv") as save, contextlib.redirect_stdout(output):
            await main.run_cli(5)
        save.assert_called_once_with(row)
        self.assertIn("OpenAlex", output.getvalue())
        self.assertIn("HTTP 429", output.getvalue())

    async def test_all_failed_search_does_not_claim_file_was_written(self):
        stats = [{"source": "OpenAlex", "status": "Error", "error": "HTTP 429"}]
        output = io.StringIO()
        with patch("builtins.input", side_effect=["graph", "q"]), \
             patch.object(main, "search_with_diagnostics_async", AsyncMock(return_value=([], stats))), \
             patch.object(main, "save_to_csv") as save, contextlib.redirect_stdout(output):
            await main.run_cli(5)
        save.assert_not_called()
        self.assertIn("All sources failed", output.getvalue())
        self.assertNotIn("Data appended", output.getvalue())
