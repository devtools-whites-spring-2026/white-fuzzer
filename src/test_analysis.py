import json
import tempfile
import unittest
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock

from src.analysis_writer import (
    _deserialize_input,
    _serialize_input,
    load_corpus_from_analysis,
    save_analysis,
)
from src.executor import ExecutionResult
from src.mutatable_request import (
    MutatableField,
    MutatableRestRequest,
    StringWithMutablePlaceholders,
)
from src.mutator import MutatableString, create_generic_mutator


def _make_mock_fuzzing_result(corpus, findings=None):
    result = MagicMock()
    result.corpus = corpus
    result.tests_to_report = findings or {}
    result.coverage_report = {"covered": 10, "total": 20, "percent": 50.0}
    result.function_coverage = (5, 10, 50.0)
    return result


class TestSerialization(unittest.TestCase):
    def test_string_roundtrip(self):
        restored = _deserialize_input(_serialize_input(MutatableString("hello world")))
        self.assertIsInstance(restored, MutatableString)
        restored = cast("MutatableString", restored)
        self.assertEqual(restored.arg, "hello world")

    def test_rest_request_roundtrip(self):
        params = StringWithMutablePlaceholders(
            data='{"page": "PAGE_VAL"}',
            placeholders=[MutatableField("PAGE_VAL", "1")],
        )
        req = MutatableRestRequest("GET", "/api/users", params=params)
        restored = _deserialize_input(_serialize_input(req))

        self.assertIsInstance(restored, MutatableRestRequest)
        restored = cast("MutatableRestRequest", restored)
        assert restored.params is not None
        assert req.params is not None
        self.assertEqual(restored.url, req.url)
        self.assertEqual(restored.params.to_string(), req.params.to_string())


class TestAnalysisWriter(unittest.TestCase):
    def test_save_and_load_analysis(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "analysis.json"
            inp = MutatableString("bad input")
            exec_result = ExecutionResult(
                thrown_exception=RuntimeError("crash!"),
                traceback_text="tb text",
                new_coverage=3,
                status_code=500,
                curl_command="curl ...",
            )
            result = _make_mock_fuzzing_result(
                corpus=[inp], findings={inp: exec_result})

            save_analysis(result, path, seed=42, iterations=100, mode="greybox")

            with path.open(encoding="utf-8") as f:
                data = json.load(f)
            loaded = load_corpus_from_analysis(path)

            self.assertEqual(data["metadata"]["seed"], 42)
            self.assertEqual(data["metadata"]["mode"], "greybox")
            self.assertEqual(len(data["findings"]), 1)
            self.assertEqual(
                data["findings"][0]["result"]["exception_type"], "RuntimeError")
            self.assertEqual(len(loaded), 1)
            self.assertIsInstance(loaded[0], MutatableString)


class TestIntegrationSaveResume(unittest.TestCase):
    def test_full_pipeline(self):
        from src.fuzzer_coordinator import orchestrate_fuzzing

        def target(s: str) -> None:
            if len(s) > 5 and s[0] == "!":
                raise ValueError("found trigger")

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "analysis.json"
            result = orchestrate_fuzzing(
                target=target,
                initial_corpus=[MutatableString("hello")],
                mutator=create_generic_mutator(),
                iterations=30,
                seed=1,
            )
            save_analysis(result, path, seed=1)
            resumed_corpus = load_corpus_from_analysis(path)

            self.assertTrue(path.exists())
            self.assertGreater(len(resumed_corpus), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
