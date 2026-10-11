import asyncio
import json
import unittest
from unittest.mock import AsyncMock, patch

import requests

from src import source_adapters as sources


def response(data=None, status=200, content=None):
    result = requests.Response()
    result.status_code = status
    result._content = content if content is not None else json.dumps(data).encode()
    return result


class SourceTests(unittest.IsolatedAsyncioTestCase):
    async def test_nullable_openalex_fields_preserve_all_records(self):
        payload = {"results": [
            {"title": "No DOI", "doi": None, "primary_location": {"source": None}, "open_access": None},
            {"title": "No location", "primary_location": None, "authorships": None},
            {"title": "Valid", "doi": "https://doi.org/10.1234/test",
             "abstract_inverted_index": {"neural": [1], "graph": [0]},
             "open_access": {"is_oa": True, "oa_url": "https://example.org/landing"},
             "best_oa_location": {"pdf_url": "https://example.org/paper.pdf"}},
        ]}
        with patch.object(sources, "make_request", AsyncMock(return_value=response(payload))):
            rows = await sources.search_openalex("graph")
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["DOI"], "")
        self.assertEqual(rows[2]["Abstract"], "graph neural")
        self.assertEqual(rows[2]["PDF"], "https://example.org/paper.pdf")

    async def test_oa_landing_page_is_not_reported_as_pdf(self):
        with patch.object(sources, "make_request", AsyncMock(return_value=response({"results": [{"title": "Test", "open_access": {"oa_url": "https://example.org/landing"}}]}))):
            rows = await sources.search_openalex("test")
        self.assertEqual(rows[0]["PDF"], "")

    async def test_openalex_key_is_passed(self):
        with patch.object(sources, "make_request", AsyncMock(return_value=response({"results": []}))) as request:
            await sources.search_openalex("test", 10, "test-key")
        self.assertEqual(request.call_args.args[1]["api_key"], "test-key")

    async def test_semantic_scholar_nullable_optional_objects(self):
        payload = {"data": [{"title": "Test", "authors": None, "externalIds": None, "openAccessPdf": None, "year": None}]}
        with patch.object(sources, "make_request", AsyncMock(return_value=response(payload))):
            rows = await sources.search_semantic_scholar("test")
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0]["Year"])

    async def test_crossref_nullable_dates_and_jats_abstract(self):
        payload = {"message": {"items": [{"title": ["Test"], "author": None, "issued": None,
                                           "container-title": [], "abstract": "<jats:p>Graphs &amp; networks</jats:p>"}]}}
        with patch.object(sources, "make_request", AsyncMock(return_value=response(payload))):
            rows = await sources.search_crossref("test", "test@example.org")
        self.assertEqual(rows[0]["Abstract"], "Graphs & networks")
        self.assertEqual(rows[0]["OAStatus"], "unknown")

    async def test_arxiv_extracts_doi_and_empty_optional_fields(self):
        xml = b'<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom"><entry><id>https://arxiv.org/abs/1234.5678</id><title>Test paper</title><arxiv:doi>10.1234/TEST</arxiv:doi></entry></feed>'
        with patch.object(sources, "make_request", AsyncMock(return_value=response(content=xml))):
            rows = await sources.search_arxiv("test")
        self.assertEqual(rows[0]["DOI"], "10.1234/test")
        self.assertIsNone(rows[0]["Year"])

    async def test_invalid_xml_is_a_source_failure(self):
        with patch.object(sources, "make_request", AsyncMock(return_value=response(content=b"not xml"))):
            rows, stats = await sources.search_all_sources("test", 5, ["arxiv"], {})
        self.assertEqual(rows, [])
        self.assertEqual(stats[0]["status"], "Error")
        self.assertEqual(stats[0]["source"], "ArXiv")

    async def test_failed_request_is_not_successful_empty_search(self):
        with patch.object(sources, "make_request", AsyncMock(return_value=None)):
            rows, stats = await sources.search_all_sources("test", 5, ["openalex"], {})
        self.assertEqual(rows, [])
        self.assertEqual(stats[0]["status"], "Error")

    async def test_successful_empty_search_is_ok(self):
        with patch.object(sources, "make_request", AsyncMock(return_value=response({"results": []}))):
            rows, stats = await sources.search_all_sources("test", 5, ["openalex"], {})
        self.assertEqual(rows, [])
        self.assertEqual(stats[0]["status"], "OK")

    async def test_malformed_records_are_skipped_with_partial_diagnostics(self):
        payload = {"results": [{"title": "Before"}, None, {}, {"title": "After"}]}
        with patch.object(sources, "make_request", AsyncMock(return_value=response(payload))):
            rows, stats = await sources.search_all_sources("test", 5, ["openalex"], {})
        self.assertEqual([row["Title"] for row in rows], ["Before", "After"])
        self.assertEqual(stats[0]["status"], "Partial")
        self.assertEqual(stats[0]["skipped_count"], 2)

    async def test_partial_failure_keeps_other_sources_and_name(self):
        with patch.object(sources, "search_openalex", AsyncMock(side_effect=sources.SourceError("Rate limit reached (HTTP 429)."))), \
             patch.object(sources, "search_arxiv", AsyncMock(return_value=[{"Source": "ArXiv", "Title": "Available"}])):
            rows, stats = await sources.search_all_sources("test", 5, ["openalex", "arxiv"], {})
        self.assertEqual(len(rows), 1)
        self.assertEqual(stats[0]["source"], "OpenAlex")
        self.assertEqual(stats[0]["status"], "Error")
        self.assertEqual(stats[1]["status"], "OK")

    async def test_output_order_is_independent_of_completion_order(self):
        async def slow(*args):
            await asyncio.sleep(0.01)
            return [{"Source": "OpenAlex", "Title": "First"}]
        progress = []
        with patch.object(sources, "search_openalex", slow), \
             patch.object(sources, "search_arxiv", AsyncMock(return_value=[{"Source": "ArXiv", "Title": "Second"}])):
            rows, _ = await sources.search_all_sources("test", 5, ["openalex", "arxiv"], {}, progress_callback=progress.append)
        self.assertEqual([row["Title"] for row in rows], ["First", "Second"])
        self.assertEqual(progress, [0.5, 1])

    async def test_google_without_credentials_reports_failure(self):
        rows, stats = await sources.search_all_sources("test", 5, ["google"], {})
        self.assertEqual(rows, [])
        self.assertEqual(stats[0]["status"], "Error")

    async def test_google_success_without_items_is_empty(self):
        with patch.object(sources, "make_request", AsyncMock(return_value=response({"searchInformation": {"totalResults": "0"}}))):
            rows = await sources.search_google("test", "key", "cx")
        self.assertEqual(rows, [])

    async def test_http_429_retries_without_sleeping_after_last_attempt(self):
        with patch.object(sources.requests, "get", return_value=response(status=429)) as get, \
             patch.object(sources.asyncio, "sleep", AsyncMock()) as sleep:
            with self.assertRaisesRegex(sources.SourceError, "429"):
                await sources.make_request("https://example.org")
        self.assertEqual(get.call_count, 3)
        self.assertEqual(sleep.await_count, 2)

    async def test_retry_can_recover(self):
        good = response({"results": []})
        with patch.object(sources.requests, "get", side_effect=[response(status=503), good]), \
             patch.object(sources.asyncio, "sleep", AsyncMock()):
            self.assertIs(await sources.make_request("https://example.org"), good)

    async def test_auth_error_is_not_retried(self):
        with patch.object(sources.requests, "get", return_value=response(status=401)) as get:
            with self.assertRaisesRegex(sources.SourceError, "401"):
                await sources.make_request("https://example.org", {"key": "secret"})
        self.assertEqual(get.call_count, 1)

    async def test_network_error_does_not_leak_request_credentials(self):
        with patch.object(sources.requests, "get", side_effect=requests.ConnectionError("https://example.org?key=secret")), \
             patch.object(sources.asyncio, "sleep", AsyncMock()):
            with self.assertRaises(sources.SourceError) as error:
                await sources.make_request("https://example.org", {"key": "secret"})
        self.assertNotIn("secret", str(error.exception))

    async def test_source_aliases_and_duplicate_sources(self):
        with patch.object(sources, "search_openalex", AsyncMock(return_value=[])) as search:
            _, stats = await sources.search_all_sources("test", 5, ["OpenAlex", "openalex"], {})
        self.assertEqual(len(stats), 1)
        search.assert_awaited_once()

    async def test_empty_sources_are_safe(self):
        self.assertEqual(await sources.search_all_sources("test", 5, [], {}), ([], []))

    async def test_invalid_search_parameters(self):
        for query, limit, selected in [("", 5, []), ("x" * 301, 5, []), ("test", 101, []), ("test", 5, ["unknown"])]:
            with self.assertRaises(ValueError):
                await sources.search_all_sources(query, limit, selected, {})
