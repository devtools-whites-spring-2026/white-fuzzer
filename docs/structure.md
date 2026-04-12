```text
fuzzer/
├── cli/
│   ├── __init__.py
│   ├── commands.py
│   ├── config_loader.py
│   └── reporter.py
│
├── core/
│   ├── __init__.py
│   ├── coordinator.py
│   └── lifecycle.py
│
├── corpus/
│   ├── __init__.py
│   ├── module.py
│   ├── storage.py
│   ├── index.py
│   └── minimizer.py
│
├── mutator/
│   ├── __init__.py
│   ├── module.py
│   ├── base.py
│   ├── selector.py
│   ├── byte.py
│   ├── dict.py
│   └── structured.py
│
├── executor/
│   ├── __init__.py
│   ├── module.py
│   ├── base.py
│   ├── process.py
│   ├── python.py
│   ├── http.py
│   ├── resource_manager.py
│   └── instrumentation/
│       ├── __init__.py
│       ├── coverage.py
│       ├── trace.py
│       ├── timeout.py
│       └── memory.py
│
├── feedback/
│   ├── __init__.py
│   ├── module.py
│   ├── analyzer.py
│   ├── decision.py
│   ├── power.py
│   └── global_state.py
│
├── storage/
│   ├── __init__.py
│   ├── seeds.py
│   ├── queue.py
│   ├── crashes.py
│   └── coverage_db.py
│
└── config/
    ├── __init__.py
    ├── builder.py
    └── default.yaml
```