import sys

sys.path.append("/your/path/to/white-fuzzer")

from pathlib import Path

from src import *
from src.executor import DjangoClientExecutor
from src.fuzzer_main import (
    print_fuzzing_result_default_formatting,
    run_fuzzer,
)
from src.mutatable_request import *
from src.mutator import *


def run_testy_fuzzer() -> None:
    executor = DjangoClientExecutor(
        settings_module="testy.root.settings.fuzzing",
        generate_user=True,
    )

    # full_spec = _extract_all_endpoint_schemas() # written by you
    full_spec = None

    executor.openapi_spec = full_spec
    initial_corpus = extract_test_cases_from_dir("/path/to/your/requests/directory")
    result = run_fuzzer(
        target=lambda x: x,
        initial_corpus=initial_corpus,
        mutator=create_generic_mutator(),
        iterations=100,
        executor=executor,
        coverage_include_paths=[
            str(Path("relevant/path/1").resolve()),
            str(Path("another/path/specific/file.py").resolve()),
        ],
        specification=full_spec,
        branch=True,
    )
    print_fuzzing_result_default_formatting(result)


def main() -> None:
    run_testy_fuzzer()


if __name__ == "__main__":
    main()
