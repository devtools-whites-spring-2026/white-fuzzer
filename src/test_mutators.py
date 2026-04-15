# from typeguard import install_import_hook

# install_import_hook()

from src.fuzzer_coordinator import orchestrate_fuzzing
from src.mutator import DeleteCharMutator, InsertCharMutator, RepeatMutator


def make_throw_if_wrong_length(expected_len: int):
    def throw_if_wrong_length(x: str) -> int:
        if len(x) != expected_len:
            raise Exception(f"Expected length {expected_len}, got {len(x)}")
        return 1

    return throw_if_wrong_length


CORPUS = ["hello"]
TARGET = make_throw_if_wrong_length(len(CORPUS[0]))


def test_delete_finds_shorter_string() -> None:
    result = orchestrate_fuzzing(
        TARGET, CORPUS.copy(), DeleteCharMutator()
    ).tests_to_report
    assert len(result) > 0
    assert any(len(s) < len(CORPUS[0]) for s in result)


def test_insert_finds_longer_string() -> None:
    result = orchestrate_fuzzing(
        TARGET, CORPUS.copy(), InsertCharMutator()
    ).tests_to_report
    assert len(result) > 0
    assert any(len(s) > len(CORPUS[0]) for s in result)


def test_repeat_finds_different_length_string() -> None:
    result = orchestrate_fuzzing(
        TARGET, CORPUS.copy(), RepeatMutator(InsertCharMutator(), max_times=5)
    ).tests_to_report
    assert len(result) > 0
    assert any(len(s) != len(CORPUS[0]) for s in result)
