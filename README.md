# White Fuzzer

A repository for a fuzzer for Django projects.
Implemented as team project on the DevTools graduate program during the Spring, 2026.

# How to run

The main supported way of running the fuzzer is via a script that calls the `run_fuzzer` main function.
The function has multiple arguments that allow for the easy use of the tool and high configurability.
The example script for fuzzer integration can be found at [docs/example-intergration.py](docs/example-integration.py).
The fuzzer supports the parsing of OpenAPI specification.
An example of this is included as part of the example linked above, with the specification extraction example for a TestY project located in [docs/example-testy-spec-extraction.py](docs/example-testy-spec-extraction.py). 

# The main function

`run_fuzzer`, as well as `run_greybox_fuzzer`, are versatile functions that allow for a very high customizability of the fuzzing process.
Their parameter include:
- `initial_corpus` --- a collection of inputs that is used as initial cases for fuzzing
- `mutator` --- a mutation strategy that shows how we mutate the input strings
- `iterations` --- the number of iterations of a fuzzer run, where iteration includes a mutation, a run of the target and an exploration of a result (measuring coverage, grading its potential in further program behavior exploration, etc.)
- `seed` --- an optional seed to allow one to reproduce the findings of a fuzzer
- `executor` --- an executor that runs an input to the fuzzer
- `coverage_include_paths` --- a filter for the files whose coverage is measured
- `branch` --- whether to enable branch coverage (the default is line coverage)
- `specification` --- a parsed OpenAPI specification that is used to derive the candidates for initial inputs

These functions are generic on the input type `T` that implements `Mutatable` interface, which allows the same main function to be used as both a function runner, and a django application runner, and is designed with extendability in mind.

The coverage is collected via [coverage.py](https://github.com/coveragepy/coveragepy) library.

# The further work

While there was a significant effort to bring this fuzzer to a production level, there is still a lot of work to be done.
The most notable fields include the following points.
- The better prioritization strategy --- the experiments show that the current strategy fails to prioritize the least explored paths, despite the implemented greybox fuzzing techniques; this need to be studies further
- The better mutation strategy --- currently a relatively naive mutator is recommended as a default mutator. This does not allow for an efficient move towards the greater coverage, and might be one of the factor that hinders the efficient program exploration.
- The constraints from the OpenApi specs --- currently their support is very basic, and it might bethe weakest part of the current work. The constraints from OpenAPI spec should be used at least as a guard for the inputs sent by the fuzzer so that we have less false positive results. A better strategy might be to forge mutators that always create inputs that satisfy the requirements.