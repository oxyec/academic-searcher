import os
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from streamlit.testing.v1 import AppTest

from src import config, source_adapters
from test_results import paper

APP = str(Path(__file__).resolve().parents[1] / "app.py")


class UiTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"ACADEMIC_SEARCH_PERSIST_STATE": "false"})
        self.env.start()
        self.addCleanup(self.env.stop)

    def app(self, rows=None, stats=None):
        at = AppTest.from_file(APP)
        if rows is not None:
            at.session_state["raw_results"] = rows
            at.session_state["source_stats"] = stats or []
            at.session_state["last_query"] = "graph"
            at.session_state["last_sources"] = ["OpenAlex"]
        return at.run(timeout=10)

    def assert_healthy(self, app):
        self.assertEqual([error.message for error in app.exception], [])

    def test_initial_screen_renders(self):
        self.assert_healthy(self.app())

    def test_server_credentials_never_fill_widgets_or_session_state(self):
        credentials = {key: f"server-only-{key}-secret" for key in ("ss", "openalex", "google", "cx")}
        email = "server-only-contact@example.test"
        with patch.object(source_adapters, "default_api_keys", return_value=credentials), patch.object(config, "UNPAYWALL_EMAIL", email):
            at = self.app()
            self.assert_healthy(at)
            for key in ("personal_ss_key_input", "personal_openalex_key_input", "personal_google_key_input", "personal_google_cx_input", "personal_crossref_email_input"):
                self.assertEqual(at.text_input(key=key).value, "")
            browser_payload = repr(at._tree) + repr(at.session_state.filtered_state)
            for secret in [*credentials.values(), email]:
                self.assertNotIn(secret, browser_payload)

    def test_legacy_credential_widget_state_is_removed(self):
        at = AppTest.from_file(APP)
        legacy_keys = ("ss_key_input", "openalex_key_input", "google_key_input", "google_cx_input", "crossref_email_input")
        for key in legacy_keys:
            at.session_state[key] = "old-server-secret"
        at.run(timeout=10)
        self.assert_healthy(at)
        for key in legacy_keys:
            self.assertNotIn(key, at.session_state.filtered_state)
        self.assertNotIn("old-server-secret", repr(at._tree))

    def test_search_uses_server_credentials_with_optional_personal_overrides(self):
        credentials = {key: f"server-{key}" for key in ("ss", "openalex", "google", "cx")}
        with patch.object(source_adapters, "default_api_keys", side_effect=lambda: credentials.copy()), patch.object(config, "UNPAYWALL_EMAIL", "server@example.test"), patch.object(source_adapters, "search_all_sources", AsyncMock(return_value=([], []))) as search:
            at = self.app()
            at.text_input(key="query_input").set_value("graph").run()
            next(button for button in at.button if button.label == "Start Search").click().run()
            self.assert_healthy(at)
            self.assertEqual(search.await_args.args[3], credentials)
            self.assertEqual(search.await_args.args[4], "server@example.test")

            at.text_input(key="personal_google_key_input").set_value(" my-key ").run()
            at.text_input(key="personal_crossref_email_input").set_value(" personal@example.test ").run()
            next(button for button in at.button if button.label == "Start Search").click().run()
            self.assert_healthy(at)
            self.assertEqual(search.await_args.args[3], {**credentials, "google": "my-key"})
            self.assertEqual(search.await_args.args[4], "personal@example.test")

    def test_single_and_zero_source_choices_do_not_crash(self):
        at = self.app()
        for selected in [["OpenAlex"], [], ["OpenAlex", "ArXiv"]]:
            at.multiselect(key="sources_input").set_value(selected).run()
            self.assert_healthy(at)

    def test_loading_setup_restores_values_before_widgets_are_created(self):
        at = self.app()
        at.text_input(key="query_input").set_value("original query").run()
        at.multiselect(key="sources_input").set_value(["OpenAlex"]).run()
        next(button for button in at.button if button.label == "Save Current Setup").click().run()
        at.text_input(key="query_input").set_value("different query").run()
        at.multiselect(key="sources_input").set_value(["ArXiv", "Crossref"]).run()
        next(button for button in at.button if button.label == "Load Selected Setup").click().run()
        self.assert_healthy(at)
        self.assertEqual(at.text_input(key="query_input").value, "original query")
        self.assertEqual(at.multiselect(key="sources_input").value, ["OpenAlex"])

    def test_all_failed_search_shows_error_and_diagnostics(self):
        at = self.app([], [{"source": "OpenAlex", "result_count": 0, "duration_sec": 0.1, "status": "Error", "error": "HTTP 429"}])
        self.assert_healthy(at)
        self.assertIn("All selected sources failed", at.error[0].value)
        self.assertEqual(len(at.dataframe), 1)

    def test_successful_empty_search_is_distinct_from_failure(self):
        at = self.app([], [{"source": "OpenAlex", "result_count": 0, "duration_sec": 0.1, "status": "OK", "error": ""}])
        self.assert_healthy(at)
        self.assertEqual(len(at.error), 0)
        self.assertIn("no matches", at.info[0].value)

    def test_partial_search_keeps_results_and_shows_warning(self):
        stats = [{"source": "ArXiv", "result_count": 0, "duration_sec": 0.1, "status": "Error", "error": "HTTP 503"}]
        at = self.app([paper()], stats)
        self.assert_healthy(at)
        self.assertTrue(any("Some sources failed" in warning.value for warning in at.warning))
        self.assertTrue(any("Title" in table.value.columns for table in at.dataframe))

    def test_text_filters_treat_regex_characters_as_literal(self):
        at = self.app([paper(Title="Graph [methods]")])
        at.text_input(key="title_filter_input").set_value("[").run()
        self.assert_healthy(at)
        self.assertFalse(any("No papers found" in warning.value for warning in at.warning))

    def test_search_button_calls_shared_source_engine(self):
        at = self.app()
        at.text_input(key="query_input").set_value("graph").run()
        at.multiselect(key="sources_input").set_value(["OpenAlex"]).run()
        stats = [{"source": "OpenAlex", "result_count": 1, "duration_sec": 0.1, "status": "OK", "error": ""}]
        # The app imports the engine on each rerun, allowing the external request boundary to be replaced.
        with patch.object(source_adapters, "search_all_sources", AsyncMock(return_value=([paper()], stats))) as search:
            next(button for button in at.button if button.label == "Start Search").click().run()
        self.assert_healthy(at)
        self.assertEqual(at.session_state["last_query"], "graph")
        self.assertEqual(at.session_state["last_sources"], ["OpenAlex"])
        search.assert_awaited_once()
