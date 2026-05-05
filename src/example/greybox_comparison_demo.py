from src.example.complex_protocol import analyze_protocol_message
from src.example.parse_http_header import parse_http_header
from src.fuzzer_coordinator import (
    orchestrate_fuzzing,
    orchestrate_greybox_fuzzing,
)
from src.main import print_fuzzing_result
from src.mutator import create_generic_mutator


def main() -> None:
    mutator = create_generic_mutator()
    result = orchestrate_fuzzing(
        parse_http_header,
        [
            "Content-Type: text/html",
            "Authorization: Bearer token123",
            "X-Request-Id: abc",
        ],
        mutator,
        iterations=500000,
    )
    print_fuzzing_result(result)

    greybox_result = orchestrate_greybox_fuzzing(
        analyze_protocol_message,
        [
            "WFZ/1 token=greybox; mode=deep; stage=7; checksum=11; action=ping",
        ],
        mutator,
        iterations=1000,
    )
    print_fuzzing_result(greybox_result)


if __name__ == "__main__":
    main()
