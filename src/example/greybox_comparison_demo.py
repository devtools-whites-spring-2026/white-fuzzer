from src.example.complex_protocol import analyze_protocol_message
from src.example.parse_http_header import parse_http_header
from src.fuzzer_main import (
    print_fuzzing_result_default_formatting,
    run_fuzzer,
    run_greybox_fuzzer,
)
from src.mutator import MutatableString, create_generic_mutator


def main() -> None:
    mutator = create_generic_mutator()
    result = run_fuzzer(
        parse_http_header,
        [
            MutatableString(s)
            for s in [
                "Content-Type: text/html",
                "Authorization: Bearer token123",
                "X-Request-Id: abc",
            ]
        ],
        mutator,
        iterations=50000,
    )
    print_fuzzing_result_default_formatting(result)

    ping = "WFZ/1 token=greybox; mode=deep; stage=7; checksum=11; action=ping"
    greybox_result = run_greybox_fuzzer(
        analyze_protocol_message,
        [
            MutatableString(ping),
        ],
        mutator,
        iterations=1000,
    )
    print_fuzzing_result_default_formatting(greybox_result)


if __name__ == "__main__":
    main()
