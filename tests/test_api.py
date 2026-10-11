import json
import unittest
from urllib.parse import urlencode
from unittest.mock import AsyncMock, patch

import api
from src import core
from src.app_utils import prepare_results
from test_results import paper


async def get(path, params):
    messages = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        messages.append(message)

    await api.app({"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "GET",
                   "scheme": "http", "path": path, "raw_path": path.encode(),
                   "query_string": urlencode(params, doseq=True).encode(), "headers": [],
                   "server": ("test", 80), "client": ("test", 1234), "root_path": ""}, receive, send)
    start = next(message for message in messages if message["type"] == "http.response.start")
    body = b"".join(message.get("body", b"") for message in messages if message["type"] == "http.response.body")
    return start["status"], json.loads(body), dict(start["headers"])


def stat(source="OpenAlex", status="OK"):
    return {"source": source, "result_count": 1 if status == "OK" else 0, "duration_sec": 0.1,
            "status": status, "error": "Failed" if status == "Error" else "", "skipped_count": 0}


class ApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_numeric_year_and_metadata_survive_response_serialization(self):
        result = {"query": "graph", "source": "OpenAlex", "title": "Test", "authors": "Author",
                  "year": 2025, "citations": 7, "abstract": "Useful abstract"}
        with patch.object(api, "search_with_diagnostics_async", AsyncMock(return_value=([result], [stat()]))):
            status, body, headers = await get("/search", {"query": "graph"})
        self.assertEqual(status, 200)
        self.assertEqual(body[0]["year"], 2025)
        self.assertEqual(body[0]["citations"], 7)
        self.assertEqual(body[0]["abstract"], "Useful abstract")
        self.assertEqual(headers[b"x-search-degraded"], b"false")

    async def test_successful_empty_search_returns_empty_list(self):
        with patch.object(api, "search_with_diagnostics_async", AsyncMock(return_value=([], [stat()]))):
            status, body, _ = await get("/search", {"query": "graph"})
        self.assertEqual((status, body), (200, []))

    async def test_complete_source_failure_returns_503_with_diagnostics(self):
        with patch.object(api, "search_with_diagnostics_async", AsyncMock(return_value=([], [stat(status="Error")]))):
            status, body, _ = await get("/search", {"query": "graph"})
        self.assertEqual(status, 503)
        self.assertEqual(body["detail"]["diagnostics"][0]["source"], "OpenAlex")

    async def test_partial_failure_is_reported_in_headers_and_report(self):
        diagnostics = [stat(), stat("ArXiv", "Error")]
        with patch.object(api, "search_with_diagnostics_async", AsyncMock(return_value=([], diagnostics))):
            status, _, headers = await get("/search", {"query": "graph"})
            report_status, report, _ = await get("/search/report", {"query": "graph"})
        self.assertEqual(status, 200)
        self.assertEqual(headers[b"x-search-degraded"], b"true")
        self.assertEqual(headers[b"x-search-failed-sources"], b"1")
        self.assertEqual(report_status, 200)
        self.assertEqual(report["diagnostics"][1]["status"], "Error")

    async def test_repeated_source_parameters_are_forwarded(self):
        with patch.object(api, "search_with_diagnostics_async", AsyncMock(return_value=([], [stat()]))) as search:
            status, _, _ = await get("/search", {"query": "graph", "sources": ["openalex", "arxiv"]})
        self.assertEqual(status, 200)
        search.assert_awaited_once_with("graph", 5, ["openalex", "arxiv"])

    async def test_api_rejects_invalid_query_and_limits(self):
        for params, expected in [({"query": " "}, 400), ({"query": "x", "limit": 0}, 422),
                                 ({"query": "x", "limit": 51}, 422), ({"query": "x" * 301}, 422)]:
            status, _, _ = await get("/search", params)
            self.assertEqual(status, expected)

    async def test_unknown_source_returns_client_error(self):
        with patch.object(api, "search_with_diagnostics_async", AsyncMock(side_effect=ValueError("Unsupported source"))):
            status, _, _ = await get("/search", {"query": "graph", "sources": "bad"})
        self.assertEqual(status, 400)

    async def test_core_and_web_preparation_have_matching_ids_order_scores(self):
        rows = [paper(), paper(DOI="", Source="ArXiv"), paper(DOI="10.1234/other", Title="Other topic", Abstract="", Year=None)]
        with patch.object(core, "search_sources", AsyncMock(return_value=(rows, [stat()]))):
            results, _ = await core.search_with_diagnostics_async("graph neural networks", 5)
        _, df = prepare_results(rows, "graph neural networks")
        self.assertEqual([row["record_id"] for row in results], df["RecordId"].tolist())
        self.assertEqual([row["score"] for row in results], df["Score"].tolist())
        self.assertEqual(len(results), 2)
        self.assertIsNone(results[1]["year"])

    async def test_compatibility_async_entry_point_remains_available(self):
        with patch.object(core, "search_sources", AsyncMock(return_value=([paper()], [stat()]))):
            rows = await core.search_all_sources_async("graph", 5)
        self.assertEqual(rows[0]["source"], "OpenAlex")
