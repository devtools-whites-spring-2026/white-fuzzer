import os
from pathlib import Path
from typing import Any

from coverage import Coverage as _CovLib
from coverage.env import PYBEHAVIOR

# sys.monitoring BRANCH_LEFT/RIGHT events were only added in Python 3.14.0a6.
# On earlier interpreter coverage.py silently falls back from sysmon to
# ctrace when branch=True. So we pick the core ourselves
_SYSMON_OK_FOR_BRANCH = PYBEHAVIOR.pep669 and getattr(
    PYBEHAVIOR, "branch_right_left", False
)
if _SYSMON_OK_FOR_BRANCH:
    os.environ.setdefault("COVERAGE_CORE", "sysmon")
else:
    os.environ.setdefault("COVERAGE_CORE", "ctrace")


class CoverageTracker:
    def __init__(
        self,
        project_root: str | None = None,
        include_paths: list[str] | None = None,
        branch: bool = False,
    ) -> None:
        self._project_root: str = project_root or str(Path.cwd())
        include_roots = include_paths or [self._project_root]
        self._include_paths: list[str] = [
            str(Path(path).resolve()) for path in include_roots
        ]
        self._branch: bool = branch
        self._started: bool = False
        self._lines_cache: dict[str, set[int]] | None = None
        self._raw_path_cache: dict[str, str] = {}
        self._last_run_lines_cache: dict[str, set[int]] | None = None
        self._last_run_context: str | None = None
        self._run_counter: int = 0
        self._cov: _CovLib = self._build_cov()

    def _build_cov(self) -> _CovLib:
        sources: list[str] = []
        include: list[str] = []
        for path_str in self._include_paths:
            path = Path(path_str)
            if path.is_file():
                include.append(path_str)
            else:
                sources.append(path_str)
        sources = list(dict.fromkeys(sources))

        # coverage.py silently ignores `include` when `source` is set, so we
        # pick one of two depending on what caller passed in
        if sources:
            return _CovLib(data_file=None, source=sources, branch=self._branch)
        return _CovLib(
            data_file=None,
            include=include or None,
            branch=self._branch,
        )

    def start(self) -> None:
        if self._started:
            return
        self._run_counter += 1
        self._last_run_context = f"fuzzer-run-{self._run_counter}"
        self._last_run_lines_cache = None
        self._cov.start()
        self._cov.switch_context(self._last_run_context)
        self._started = True
        self._lines_cache = None

    def stop(self) -> None:
        if not self._started:
            return
        self._cov.stop()
        self._started = False
        self._lines_cache = None
        self._last_run_lines_cache = None

    def reset(self) -> None:
        if self._started:
            self._cov.stop()
            self._started = False
        self._cov = self._build_cov()
        self._lines_cache = None
        self._raw_path_cache = {}
        self._last_run_lines_cache = None
        self._last_run_context = None
        self._run_counter = 0

    @staticmethod
    def _normalize(path: str) -> str:
        return str(Path(path).resolve())

    def get_coverage(self) -> dict[str, set[int]]:
        if self._lines_cache is None:
            data = self._cov.get_data()
            self._lines_cache = {
                self._normalize(fn): set(data.lines(fn) or ())
                for fn in data.measured_files()
            }
        return self._lines_cache

    def get_coverage_of(self, filename: str) -> set[int]:
        collector = getattr(self._cov, "_collector", None)
        if collector is not None:
            collector.flush_data()
        data = getattr(self._cov, "_data", None)
        if data is None:
            return set()

        lines = data.lines(filename)
        if lines is None:
            key = self._normalize(filename)
            if key != filename:
                lines = data.lines(key)
            if lines is None:
                raw = self._raw_path_cache.get(key)
                if raw is None:
                    for fn in data.measured_files():
                        if self._normalize(fn) == key:
                            raw = fn
                            self._raw_path_cache[key] = fn
                            break
                if raw is not None:
                    lines = data.lines(raw)

        return set(lines or ())

    def get_last_run_coverage(self) -> dict[str, set[int]]:
        if self._last_run_context is None:
            return {}
        if self._last_run_lines_cache is None:
            data = self._cov.get_data()
            data.set_query_context(self._last_run_context)
            try:
                self._last_run_lines_cache = {
                    self._normalize(fn): set(data.lines(fn) or ())
                    for fn in data.measured_files()
                }
            finally:
                data.set_query_contexts(None)
        return self._last_run_lines_cache

    def _iter_source_files(self):
        seen: set[str] = set()
        for path_str in self._include_paths:
            path = Path(path_str)
            if path.is_file() and path.suffix == ".py":
                key = str(path)
                if key not in seen:
                    seen.add(key)
                    yield key
            elif path.is_dir():
                for root, _, files in os.walk(path):
                    for file in files:
                        if file.endswith(".py"):
                            key = str(Path(root) / file)
                            if key not in seen:
                                seen.add(key)
                                yield key

    def get_stats(self) -> dict[str, Any]:
        total = 0
        covered = 0
        branches_total = 0
        branches_covered = 0
        for fn in self._iter_source_files():
            try:
                analysis = self._cov._analyze(fn)
            except Exception:
                continue
            nums = analysis.numbers
            total += nums.n_statements
            covered += nums.n_statements - nums.n_missing
            if self._branch:
                branches_total += nums.n_branches
                branches_covered += nums.n_branches - nums.n_missing_branches
        percent = round(covered / total * 100, 2) if total else 0.0
        branches_percent = (
            round(branches_covered / branches_total * 100, 2) if branches_total else 0.0
        )
        return {
            "covered": covered,
            "total": total,
            "percent": percent,
            "branches_covered": branches_covered,
            "branches_total": branches_total,
            "branches_percent": branches_percent,
        }

    def export(self, output_dir: str, formats: list[str]) -> None:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        if "html" in formats:
            self._cov.html_report(directory=str(out / "htmlcov"))
        if "json" in formats:
            self._cov.json_report(outfile=str(out / "coverage.json"))
        if "xml" in formats:
            self._cov.xml_report(outfile=str(out / "coverage.xml"))
        if "lcov" in formats:
            self._cov.lcov_report(outfile=str(out / "coverage.lcov"))
