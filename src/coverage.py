import os
import sys
from pathlib import Path
from types import CodeType
from typing import Any


class Coverage:
    def __init__(
        self,
        project_root: str | None = None,
        include_paths: list[str] | None = None,
    ) -> None:
        self._filename_to_covered_lines: dict[str, set[int]] = {}
        self._tool_id: int = sys.monitoring.COVERAGE_ID
        self._started: bool = False

        self._project_root: str = project_root or str(Path.cwd())
        include_roots = include_paths or [self._project_root]
        self._include_paths: list[str] = [
            str(Path(path).resolve()) for path in include_roots
        ]

        self._include_files: set[str] = set()
        self._include_dir_prefixes: list[str] = []
        for path in self._include_paths:
            p = Path(path)
            if p.is_file():
                self._include_files.add(path)
            elif p.is_dir():
                self._include_dir_prefixes.append(path + os.sep)

        self._scope_cache: dict[CodeType, set[int]] = {}
        self._out_of_scope: set[CodeType] = set()
        self._total_lines_map: dict[str, set[int]] = self._collect_total_lines()

    def _is_in_scope(self, filename: str) -> bool:
        if filename in self._include_files:
            return True
        return any(
            filename.startswith(prefix) for prefix in self._include_dir_prefixes
        )

    def _line_callback(self, code: CodeType, line_number: int):
        bucket = self._scope_cache.get(code)
        if bucket is not None:
            bucket.add(line_number)
            return None
        if code in self._out_of_scope:
            return sys.monitoring.DISABLE
        resolved = str(Path(code.co_filename).resolve())
        if not self._is_in_scope(resolved):
            self._out_of_scope.add(code)
            return sys.monitoring.DISABLE
        bucket = self._filename_to_covered_lines.get(resolved)
        if bucket is None:
            bucket = set()
            self._filename_to_covered_lines[resolved] = bucket
        self._scope_cache[code] = bucket
        bucket.add(line_number)
        return None

    def start(self) -> None:
        if self._started:
            return

        sys.monitoring.use_tool_id(self._tool_id, "coverage")

        sys.monitoring.register_callback(
            self._tool_id, sys.monitoring.events.LINE, self._line_callback
        )

        sys.monitoring.set_events(self._tool_id, sys.monitoring.events.LINE)

        self._started = True

    def stop(self) -> None:
        if not self._started:
            return

        sys.monitoring.set_events(self._tool_id, 0)
        sys.monitoring.register_callback(
            self._tool_id, sys.monitoring.events.LINE, None
        )
        sys.monitoring.free_tool_id(self._tool_id)
        self._started = False

    # tmp with settrace for Testy
    # def _trace(self, frame, event, arg):
    #     if event == "call":
    #         filename = str(Path(frame.f_code.co_filename).resolve())
    #         if not self._is_in_scope(filename):
    #             return None
    #         return self._trace
    #     if event == "line":
    #         filename = str(Path(frame.f_code.co_filename).resolve())
    #         if self._is_in_scope(filename):
    #             self._covered_lines.add((filename, frame.f_lineno))
    #     return self._trace

    # def start(self) -> None:
    #     if self._started:
    #         return
    #     sys.settrace(self._trace)
    #     self._started = True

    # def stop(self) -> None:
    #     if not self._started:
    #         return
    #     sys.settrace(None)
    #     self._started = False

    # end settrace

    def reset(self) -> None:
        self._filename_to_covered_lines.clear()
        self._scope_cache.clear()
        self._out_of_scope.clear()
        if self._started:
            sys.monitoring.restart_events()

    def get_coverage(self) -> dict[str, set[int]]:
        return self._filename_to_covered_lines

    def _get_file_lines(self, filename: str) -> set[int]:
        lines: set[int] = set()

        try:
            with Path(filename).open() as f:
                for i, line in enumerate(f, start=1):
                    stripped_line: str = line.strip()

                    if stripped_line and not stripped_line.startswith("#"):
                        lines.add(i)
        except Exception:
            pass

        return lines

    def _collect_total_lines(self) -> dict[str, set[int]]:
        result: dict[str, set[int]] = {}

        for path in self._include_paths:
            path_obj = Path(path)

            if path_obj.is_file():
                full_path = str(path_obj.resolve())
                result[full_path] = self._get_file_lines(full_path)

            elif path_obj.is_dir():
                for root, _, files in os.walk(path):
                    for file in files:
                        if file.endswith(".py"):
                            full_path = str(Path(root) / file)
                            result[full_path] = self._get_file_lines(full_path)

        return result

    def get_stats(self) -> dict[str, Any]:
        total_covered: int = 0
        total_lines: int = 0
        for filename, all_lines in self._total_lines_map.items():
            covered = self._filename_to_covered_lines.get(filename)
            if covered is not None:
                total_covered += len(covered & all_lines)
            total_lines += len(all_lines)

        percent: float = (
            (total_covered / total_lines * 100) if total_lines else 0.0
        )

        return {
            "covered": total_covered,
            "total": total_lines,
            "percent": round(percent, 2),
        }
