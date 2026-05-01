# White Fuzzer

A public repository.

# To run

After initializing a virtual environment, run the main module with `--help` argument:
```
> python -m src.main --help
usage: main.py [-h] [--function FUNCTION] [--iterations ITERATIONS] [--seed SEED] [--input INPUT [INPUT ...]] [--verbose] [--greybox] target

Fuzzer CLI

positional arguments:
  target                Path to python file to fuzz

options:
  -h, --help            show this help message and exit
  --function FUNCTION   Function name to fuzz (default: main)
  --iterations ITERATIONS
  --seed SEED
  --input INPUT [INPUT ...]
  --verbose
  --greybox
```

A working example:
```
python -m src.main --function analyze_protocol_message  --iterations 10000 src/example/complex_protocol.py --input  "WFZ/1 token=greybox; mode=deep; stage=7; checksum=11; action=ping"
```