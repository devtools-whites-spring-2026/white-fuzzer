# from typeguard import install_import_hook

# install_import_hook()
from src.fuzzer_coordinator import orchestrate_fuzzing
from src.mutator import RandomCharMutator
from src.throw_on_digit import throw_if_1st_is_digit


def main() -> None:
    result = orchestrate_fuzzing(
        throw_if_1st_is_digit, ["hello"], RandomCharMutator()
    )
    print(result)


if __name__ == "__main__":
    main()
