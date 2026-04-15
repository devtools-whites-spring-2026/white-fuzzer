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
        self.covered_lines: set[tuple[str, int]] = set()
        self.tool_id: int = 5
        self._started: bool = False

        self._project_root: str = project_root or str(Path.cwd())
        self._include_paths: list[str] = include_paths or [self._project_root]

        self._total_lines_map: dict[str, set[int]] = self._collect_total_lines()

    def _line_callback(self, code: CodeType, line_number: int) -> None:
        filename: str = code.co_filename

        if not filename.startswith(self._project_root):
            return

        self.covered_lines.add((filename, line_number))

    def start(self) -> None:
        if self._started:
            return

        sys.monitoring.use_tool_id(self.tool_id, "coverage")

        sys.monitoring.register_callback(
            self.tool_id, sys.monitoring.events.LINE, self._line_callback
        )

        sys.monitoring.set_events(self.tool_id, sys.monitoring.events.LINE)

        self._started = True

    def stop(self) -> None:
        if not self._started:
            return

        sys.monitoring.set_events(self.tool_id, 0)
        sys.monitoring.register_callback(
            self.tool_id, sys.monitoring.events.LINE, None
        )
        sys.monitoring.free_tool_id(self.tool_id)
        self._started = False

    def reset(self) -> None:
        self.covered_lines.clear()

    def get_coverage(self) -> set[tuple[str, int]]:
        return self.covered_lines

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
                result[path] = self._get_file_lines(path)

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
            covered: set[int] = {
                line for (f, line) in self.covered_lines if f == filename
            }

            covered_count: int = len(covered & all_lines)
            total_count: int = len(all_lines)

            total_covered += covered_count
            total_lines += total_count

        percent: float = (
            (total_covered / total_lines * 100) if total_lines else 0.0
        )

        return {
            "covered": total_covered,
            "total": total_lines,
            "percent": round(percent, 2),
        }
