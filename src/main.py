from typeguard import install_import_hook, typechecked

# install_import_hook must come before all other imports
# to enable runtime typechecking within them
install_import_hook()

import argparse


@typechecked
def main() -> None:
    parser = argparse.ArgumentParser(description="White fuzzer")
    parser.parse_args()

    print("CLI Invoked")


if __name__ == "__main__":
    main()
