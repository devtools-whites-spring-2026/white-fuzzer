import sys
import os
from typing import Dict, Set, Tuple


class Coverage:
    def __init__(self, project_root=None, include_paths=None):
        self.covered_lines: Set[Tuple[str, int]] = set()
        self.tool_id = 5
        self._started = False
        
        self._project_root = project_root or os.getcwd()
        self._include_paths = include_paths or [self._project_root]

        self._total_lines_map: Dict[str, Set[int]] = self._collect_total_lines()

    def _line_callback(self, code, line_number):
        filename = code.co_filename
        if not filename.startswith(self._project_root):
            return
        
        self.covered_lines.add((filename, line_number))

    def start(self):
        if self._started:
            return

        sys.monitoring.use_tool_id(self.tool_id, "coverage")

        sys.monitoring.register_callback(
            self.tool_id,
            sys.monitoring.events.LINE,
            self._line_callback
        )

        sys.monitoring.set_events(
            self.tool_id,
            sys.monitoring.events.LINE
        )

        self._started = True

    def stop(self):
        if not self._started:
            return

        sys.monitoring.set_events(self.tool_id, 0)
        self._started = False

    def reset(self):
        self.covered_lines.clear()

    def get_coverage(self):
        return self.covered_lines
    
    def _get_file_lines(self, filename):
        lines = set()

        try:
            with open(filename, "r") as f:
                for i, line in enumerate(f, start=1):
                    stripped_line = line.strip()

                    if stripped_line and not stripped_line.startswith("#"):
                        lines.add(i)
        except Exception:
            pass

        return lines

    def _collect_total_lines(self):
        result = {}

        for path in self._include_paths:
            if os.path.isfile(path):
                result[path] = self._get_file_lines(path)

            elif os.path.isdir(path):
                for root, _, files in os.walk(path):
                    for file in files:
                        if file.endswith(".py"):
                            full_path = os.path.join(root, file)
                            result[full_path] = self._get_file_lines(full_path)

        return result

    def get_stats(self):
        total_covered = 0
        total_lines = 0

        for filename, all_lines in self._total_lines_map.items():
            covered = {l for (f, l) in self.covered_lines if f == filename}

            covered_count = len(covered & all_lines)
            total_count = len(all_lines)

            total_covered += covered_count
            total_lines += total_count

        percent = (total_covered / total_lines * 100) if total_lines else 0

        return {
            "covered": total_covered,
            "total": total_lines,
            "percent": round(percent, 2),
        }