# Epilogue

Epilogue is a batch-only observability library. It records execution data while a
workload runs and persists that data for post-processing after the fact. It does
not provide live subscribers, online analysis, callbacks, or application-specific
instrumentation.

## Compile-time observation contract

The native API is header-only:

```cpp
#include <epilogue/batch_monitor.hpp>

struct Observation final
{
  int value;
};

struct Encoder final
{
  static std::string encode(const Observation& observation)
  {
    return "{\"value\":" + std::to_string(observation.value) + "}";
  }
};

epilogue::BatchMonitor<Observation, Encoder, 256UL> monitor{
  "path/to/ledger.ndjson"
};

monitor.log("execute", Observation{42});
monitor.flush();
```

The embedding project selects `Observation` and `Encoder` at compile time.
Epilogue never includes or depends on the embedding project's domain types. The
encoder must return one valid JSON value for the observation.

## Batch behavior

Records stay in memory until the configured batch size is reached, `flush()` is
called, or the monitor is destroyed. Each persisted line is an independent JSON
record containing:

- `sequence`: process-local monotonically increasing record number.
- `timestamp_ns`: wall-clock timestamp in nanoseconds since the Unix epoch.
- `operation`: the application-supplied operation name.
- `observation`: the JSON value emitted by the compile-time encoder.

The ledger is append-only NDJSON so it can be streamed or post-processed without
loading the entire run into memory.

## Storage ownership

Epilogue accepts a destination path from the embedding application. Storage
layout is therefore owned by the application or platform. For example, a system
with a Linux-style local filesystem can place Epilogue ledgers under its own
`/var/log/epilogue` hierarchy without teaching Epilogue anything about that
filesystem implementation.
