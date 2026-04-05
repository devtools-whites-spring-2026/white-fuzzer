```mermaid
graph TB
    subgraph "CLI Layer"
        CLIParser[Command Parser]
        ConfigLoader[Config Loader<br/>YAML/JSON]
        Reporter[Reporter<br/>Progress & Stats]
    end
    
    subgraph "Orchestration Layer"
        Coordinator[Fuzzing Coordinator]
        Timer[Execution Timer]
        StopCondition[Stop Condition Checker]
        StatsCollector[Statistics Collector]
    end
    
    subgraph "Corpus Module"
        subgraph "Corpus Components"
            CorpusStorage[Corpus Storage]
            CorpusIndex[Index Manager]
            Minimizer[Corpus Minimizer]
            Serializer[Serializer<br/>pickle/msgpack]
        end
        
        subgraph "Corpus Data"
            SeedQueue[Seed Queue]
            InterestingSet[Interesting Set]
            FavoritesList[Favorites List<br/>in AFL]
        end
    end
    
    subgraph "Mutator Module"
        subgraph "Base Mutators"
            ByteMutator[Byte Mutator<br/>AFL-style]
            DictMutator[Dictionary Mutator<br/>Tokens]
        end
        
        subgraph "Advanced Mutators"
            StructMutator[Structured Mutator<br/>JSON/Protobuf]
            LLMMutator[LLM Mutator<br/>Intelligent]
        end
        
        MutatorSelector[Mutator Adapter]
    end
    
    subgraph "Executor Module"
        subgraph "Executors"
            ProcessExec[Process Executor<br/>fork+exec]
            PythonExec[Python Executor<br/>in-process]
            HTTPExec[HTTP Executor<br/>REST API]
        end
        
        subgraph "Instrumentation"
            CoverageCollector[Coverage Collector<br/>SanitizerCoverage]
            TraceCollector[Trace Collector<br/>Branch tracing]
            TimeoutHandler[Timeout Handler]
            MemoryLimit[Memory Limiter]
        end
        
        ResourceManager[Resource Manager<br/>Process pool]
    end
    
    subgraph "Feedback Module"
        subgraph "Analyzers"
            CoverageAnalyzer[Coverage Analyzer<br/>New edges?]
            CrashAnalyzer[Crash Analyzer<br/>Unique crash?]
            PerfAnalyzer[Performance Analyzer<br/>Slowdown?]
        end
        
        subgraph "Decision Logic"
            InterestingDecider[Interesting Decider]
            PowerCalculator[Power Calculator<br/>in AFL]
            CorpusUpdater[Corpus Updater]
        end
        
        GlobalState[Global Coverage Map<br/>Edge hit counts]
    end
    
    subgraph "Storage Layer"
        FileStorage[(File System<br/>corpus/crashes/)]
        MetadataDB[(Metadata DB<br/>PgSQL/SQLite)]
        CoverageDB[(Coverage DB<br/>Bitmaps)]
    end
    
    subgraph "External Targets"
        PythonTarget[Python Functions]
        NativeBinary[Native Binaries]
        RESTTarget[REST APIs]
    end
    
    CLIParser --> Coordinator
    ConfigLoader --> Coordinator
    Coordinator --> Timer
    Coordinator --> StopCondition
    Coordinator --> StatsCollector
    StatsCollector --> Reporter
    
    Coordinator --> CorpusStorage
    Coordinator --> MutatorSelector
    Coordinator --> ResourceManager
    Coordinator --> InterestingDecider
    
    CorpusStorage --> SeedQueue
    CorpusStorage --> InterestingSet
    CorpusStorage --> FavoritesList
    CorpusStorage --> Serializer
    CorpusStorage --> Minimizer
    
    MutatorSelector --> ByteMutator
    MutatorSelector --> DictMutator
    MutatorSelector --> HavocMutator
    MutatorSelector --> SpliceMutator
    MutatorSelector --> StructMutator
    MutatorSelector --> LLMMutator
    
    ResourceManager --> ProcessExec
    ResourceManager --> PythonExec
    ResourceManager --> HTTPExec
    ResourceManager --> QEMUExec
    
    ProcessExec --> CoverageCollector
    ProcessExec --> TraceCollector
    ProcessExec --> TimeoutHandler
    ProcessExec --> MemoryLimit
    
    PythonExec --> CoverageCollector
    
    ProcessExec --> NativeBinary
    PythonExec --> PythonTarget
    HTTPExec --> RESTTarget
    QEMUExec --> NativeBinary
    
    CoverageCollector --> CoverageAnalyzer
    TraceCollector --> CoverageAnalyzer
    TimeoutHandler --> CrashAnalyzer
    MemoryLimit --> CrashAnalyzer
    
    CoverageAnalyzer --> InterestingDecider
    CrashAnalyzer --> InterestingDecider
    PerfAnalyzer --> InterestingDecider
    
    InterestingDecider --> PowerCalculator
    InterestingDecider --> CorpusUpdater
    
    PowerCalculator --> MutatorSelector
    
    CorpusStorage --> FileStorage
    CorpusStorage --> MetadataDB
    CoverageAnalyzer --> GlobalState
    GlobalState --> CoverageDB
```