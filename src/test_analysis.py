import json
import os
import tempfile
import unittest
from typing import cast
from unittest.mock import MagicMock

from src.analysis_writer import (
    _deserialize_input,
    _serialize_input,
    load_corpus_from_analysis,
    save_analysis,
)
from src.executor import ExecutionResult, _build_curl_command
from src.mutatable_request import (
    MutatableField,
    MutatableRestRequest,
    StringWithMutablePlaceholders,
)
from src.mutator import MutatableString


class TestExecutionResultToDict(unittest.TestCase):
    def test_no_exception(self):
        r = ExecutionResult(thrown_exception=None, traceback_text=None, new_coverage=5)
        d = r.to_dict()
        self.assertIsNone(d["exception_type"])
        self.assertIsNone(d["exception_message"])
        self.assertEqual(d["new_coverage"], 5)
        self.assertIsNone(d["status_code"])
        self.assertIsNone(d["curl_command"])

    def test_with_exception(self):
        exc = ValueError("bad input")
        r = ExecutionResult(
            thrown_exception=exc, traceback_text="Traceback...", new_coverage=0
        )
        d = r.to_dict()
        self.assertEqual(d["exception_type"], "ValueError")
        self.assertEqual(d["exception_message"], "bad input")
        self.assertEqual(d["traceback"], "Traceback...")

    def test_with_http_fields(self):
        r = ExecutionResult(
            thrown_exception=None,
            traceback_text=None,
            status_code=404,
            curl_command='curl -X GET "/api/items"',
        )
        d = r.to_dict()
        self.assertEqual(d["status_code"], 404)
        self.assertEqual(d["curl_command"], 'curl -X GET "/api/items"')

    def test_to_dict_is_json_serializable(self):
        exc = RuntimeError("oops")
        r = ExecutionResult(
            thrown_exception=exc,
            traceback_text="tb",
            new_coverage=2,
            status_code=500,
            curl_command="curl ...",
        )
        json.dumps(r.to_dict())


class TestBuildCurlCommand(unittest.TestCase):
    def test_get_no_params(self):
        cmd = _build_curl_command("GET", "/api/items", None, None)
        self.assertIn("-X GET", cmd)
        self.assertIn("/api/items", cmd)
        self.assertNotIn("-d", cmd)

    def test_get_with_params(self):
        cmd = _build_curl_command("GET", "/api/items", '{"page": "1"}', None)
        self.assertIn("page=1", cmd)
        self.assertNotIn("-d", cmd)

    def test_post_with_body(self):
        cmd = _build_curl_command("POST", "/api/users", None, '{"name": "alice"}')
        self.assertIn("-X POST", cmd)
        self.assertIn("Content-Type: application/json", cmd)
        self.assertIn('{"name": "alice"}', cmd)

    def test_invalid_json_params_fallback(self):
        cmd = _build_curl_command("GET", "/api/items", "not-json", None)
        self.assertIn("/api/items", cmd)


class TestMutatableStringSerialization(unittest.TestCase):
    def test_serialize_deserialize_roundtrip(self):
        original = MutatableString("hello world")
        serialized = _serialize_input(original)
        self.assertEqual(serialized["kind"], "string")
        self.assertEqual(serialized["value"], "hello world")

        restored = _deserialize_input(serialized)
        self.assertIsInstance(restored, MutatableString)
        restored = cast("MutatableString", restored)
        self.assertEqual(restored.arg, "hello world")
        self.assertEqual(repr(restored), repr(original))

    def test_serialize_empty_string(self):
        s = MutatableString("")
        d = _serialize_input(s)
        restored = _deserialize_input(d)
        self.assertIsInstance(restored, MutatableString)
        restored = cast("MutatableString", restored)
        self.assertEqual(restored.arg, "")

    def test_serialize_special_chars(self):
        s = MutatableString('{"key": "val\\nue"}')
        d = _serialize_input(s)
        restored = _deserialize_input(d)
        self.assertIsInstance(restored, MutatableString)
        restored = cast("MutatableString", restored)
        self.assertEqual(restored.arg, s.arg)


class TestMutatableRestRequestSerialization(unittest.TestCase):
    def _make_request(self):
        params = StringWithMutablePlaceholders(
            data='{"page": "PAGE_VAL"}',
            placeholders=[MutatableField("PAGE_VAL", "1")],
        )
        body = StringWithMutablePlaceholders(
            data='{"name": "NAME_VAL"}',
            placeholders=[MutatableField("NAME_VAL", "alice")],
        )
        return MutatableRestRequest("POST", "/api/users", params=params, data=body)

    def test_to_dict_structure(self):
        req = self._make_request()
        d = req.to_dict()
        self.assertEqual(d["type"], "POST")
        self.assertEqual(d["url"], "/api/users")
        self.assertIsNotNone(d["params"])
        self.assertIsNotNone(d["data"])

    def test_roundtrip(self):
        req = self._make_request()
        d = req.to_dict()
        restored = MutatableRestRequest.from_dict(d)
        self.assertEqual(restored.type, req.type)
        self.assertEqual(restored.url, req.url)
        assert restored.params is not None
        assert restored.data is not None
        assert req.params is not None
        assert req.data is not None
        self.assertEqual(restored.params.to_string(), req.params.to_string())
        self.assertEqual(restored.data.to_string(), req.data.to_string())

    def test_serialize_deserialize_via_helpers(self):
        req = self._make_request()
        serialized = _serialize_input(req)
        self.assertEqual(serialized["kind"], "rest_request")
        restored = _deserialize_input(serialized)
        self.assertIsInstance(restored, MutatableRestRequest)
        restored = cast("MutatableRestRequest", restored)
        self.assertEqual(restored.url, req.url)

    def test_no_params_no_data(self):
        req = MutatableRestRequest("GET", "/api/health")
        d = req.to_dict()
        self.assertIsNone(d["params"])
        self.assertIsNone(d["data"])
        restored = MutatableRestRequest.from_dict(d)
        self.assertIsNone(restored.params)
        self.assertIsNone(restored.data)

    def test_to_dict_is_json_serializable(self):
        req = self._make_request()
        json.dumps(_serialize_input(req))


class TestStringWithMutablePlaceholdersSerialization(unittest.TestCase):
    def test_roundtrip(self):
        obj = StringWithMutablePlaceholders(
            data="hello PLACE",
            placeholders=[MutatableField("PLACE", "world")],
        )
        d = obj.to_dict()
        restored = StringWithMutablePlaceholders.from_dict(d)
        self.assertEqual(restored.to_string(), obj.to_string())
        self.assertEqual(restored.data, obj.data)
        self.assertEqual(len(restored.placeholders), 1)
        self.assertEqual(restored.placeholders[0].value, "world")

    def test_multiple_placeholders(self):
        obj = StringWithMutablePlaceholders(
            data='{"a": "A", "b": "B"}',
            placeholders=[MutatableField("A", "foo"), MutatableField("B", "bar")],
        )
        restored = StringWithMutablePlaceholders.from_dict(obj.to_dict())
        self.assertEqual(len(restored.placeholders), 2)
        self.assertEqual(restored.to_string(), obj.to_string())


class TestDeserializeUnknownKind(unittest.TestCase):
    def test_raises_on_unknown_kind(self):
        with self.assertRaises(ValueError):
            _deserialize_input({"kind": "foobar"})


def _make_mock_fuzzing_result(corpus, findings=None):
    result = MagicMock()
    result.corpus = corpus
    result.tests_to_report = findings or {}
    result.coverage_report = {
        "covered": 10,
        "total": 20,
        "percent": 50.0,
        "branches_covered": 4,
        "branches_total": 8,
        "branches_percent": 50.0,
    }
    result.function_coverage = (5, 10, 50.0)
    return result


class TestSaveAndLoadAnalysis(unittest.TestCase):
    def test_save_creates_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "analysis.json")
            result = _make_mock_fuzzing_result([MutatableString("hello")])
            save_analysis(
                result,
                path,
                seed=42,
                iterations=100,
                target="target.py",
                mode="blackbox",
            )
            self.assertTrue(os.path.exists(path))

    def test_saved_json_is_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "analysis.json")
            result = _make_mock_fuzzing_result([MutatableString("hello")])
            save_analysis(
                result,
                path,
                seed=42,
                iterations=100,
                target="target.py",
                mode="greybox",
            )
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data["metadata"]["seed"], 42)
            self.assertEqual(data["metadata"]["mode"], "greybox")
            self.assertEqual(data["metadata"]["iterations"], 100)
            self.assertEqual(data["coverage"]["covered"], 10)
            self.assertEqual(data["function_coverage"]["covered"], 5)

    def test_corpus_roundtrip_string(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "analysis.json")
            corpus = [MutatableString("foo"), MutatableString("bar baz")]
            result = _make_mock_fuzzing_result(corpus)
            save_analysis(result, path)

            loaded = load_corpus_from_analysis(path)
            self.assertEqual(len(loaded), 2)
            self.assertIsInstance(loaded[0], MutatableString)
            self.assertIsInstance(loaded[1], MutatableString)
            first = cast("MutatableString", loaded[0])
            second = cast("MutatableString", loaded[1])
            self.assertEqual(first.arg, "foo")
            self.assertEqual(second.arg, "bar baz")

    def test_corpus_roundtrip_rest_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "analysis.json")
            params = StringWithMutablePlaceholders(
                data='{"q": "QVAL"}',
                placeholders=[MutatableField("QVAL", "test")],
            )
            req = MutatableRestRequest("GET", "/api/search", params=params)
            result = _make_mock_fuzzing_result([req])
            save_analysis(result, path)

            loaded = load_corpus_from_analysis(path)
            self.assertEqual(len(loaded), 1)
            self.assertIsInstance(loaded[0], MutatableRestRequest)
            item = cast("MutatableRestRequest", loaded[0])
            assert item.params is not None
            self.assertEqual(item.url, "/api/search")
            self.assertEqual(item.params.to_string(), params.to_string())

    def test_findings_serialized(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "analysis.json")
            inp = MutatableString("bad input")
            exc = RuntimeError("crash!")
            exec_result = ExecutionResult(
                thrown_exception=exc,
                traceback_text="tb text",
                new_coverage=3,
                status_code=500,
                curl_command="curl ...",
            )
            result = _make_mock_fuzzing_result(
                corpus=[inp], findings={inp: exec_result}
            )
            save_analysis(result, path)

            with open(path, encoding="utf-8") as f:
                data = json.load(f)

            findings = data["findings"]
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0]["input_repr"], "bad input")
            self.assertEqual(findings[0]["result"]["exception_type"], "RuntimeError")
            self.assertEqual(findings[0]["result"]["exception_message"], "crash!")
            self.assertEqual(findings[0]["result"]["status_code"], 500)
            self.assertEqual(findings[0]["result"]["curl_command"], "curl ...")

    def test_save_creates_parent_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "nested", "dir", "analysis.json")
            result = _make_mock_fuzzing_result([MutatableString("x")])
            save_analysis(result, path)
            self.assertTrue(os.path.exists(path))

    def test_load_empty_corpus(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "analysis.json")
            result = _make_mock_fuzzing_result([])
            save_analysis(result, path)
            loaded = load_corpus_from_analysis(path)
            self.assertEqual(loaded, [])

    def test_none_seed_saved_as_null(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "analysis.json")
            result = _make_mock_fuzzing_result([MutatableString("x")])
            save_analysis(result, path, seed=None)
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            self.assertIsNone(data["metadata"]["seed"])


class TestIntegrationSaveResume(unittest.TestCase):
    def test_full_pipeline(self):
        from src.fuzzer_coordinator import orchestrate_fuzzing
        from src.mutator import create_generic_mutator

        def target(s: str) -> None:
            if len(s) > 5 and s[0] == "!":
                raise ValueError("found trigger")

        mutator = create_generic_mutator()

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "analysis.json")

            result1 = orchestrate_fuzzing(
                target=target,
                initial_corpus=[MutatableString("hello")],
                mutator=mutator,
                iterations=50,
                seed=1,
            )
            save_analysis(
                result1, path, seed=1, iterations=50, target="inline", mode="blackbox"
            )

            self.assertTrue(os.path.exists(path))

            resumed_corpus = load_corpus_from_analysis(path)
            self.assertGreater(len(resumed_corpus), 0)
            for item in resumed_corpus:
                self.assertIsInstance(item, MutatableString)

            result2 = orchestrate_fuzzing(
                target=target,
                initial_corpus=resumed_corpus + [MutatableString("hello")],
                mutator=mutator,
                iterations=30,
                seed=2,
            )
            self.assertIsNotNone(result2)
            save_analysis(
                result2, path, seed=2, iterations=30, target="inline", mode="blackbox"
            )
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data["metadata"]["seed"], 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
