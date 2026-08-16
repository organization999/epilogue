# Epilogue

Epilogue is a Python 3, batch-only observability library. It records ordinary
Python data while a workload runs and persists that data for post-processing
after the fact. It does not know about UNI expressions, C++ types, or any other
application-specific domain model.

## Generic observation contract

The embedding application defines the observation schema. Epilogue only requires
that the supplied value can be serialized by Python's `json` module.

```python
from epilogue import BatchMonitor

expression = {
    'version': 2,
    'tokens': [
        {'kind': 0, 'value': 0},
    ],
    'literals': [42.0],
}

monitor: BatchMonitor[dict[str, object]] = BatchMonitor(
    'path/to/ledger.ndjson',
    batch_size=256,
)

monitor.log('expression.execute', expression)
monitor.flush()
```

The application owns the meaning and shape of `expression`. Epilogue treats it
as opaque Python data.

## Batch behavior

Records remain in memory until the configured batch size is reached or `flush()`
/ `close()` is called. Each persisted line contains:

- `sequence`: process-local monotonically increasing record number.
- `timestamp_ns`: wall-clock timestamp in nanoseconds since the Unix epoch.
- `operation`: the application-supplied operation name.
- `observation`: the application-supplied Python value.

The ledger is append-only NDJSON so post-processing can stream records without
loading the complete run into memory.

## Storage ownership

Epilogue accepts a destination path from the embedding application. It uses
normal Python filesystem APIs, so a host application may route those calls
through its own filesystem layer. UNI, for example, can place the ledger under
its LFS `/var/log/epilogue` hierarchy without adding LFS knowledge to Epilogue.

## Python only

Epilogue has no native C++ API and no pybind11 dependency. Native applications
that want to use Epilogue should expose their observation data at the Python
boundary and let Python own batching and persistence.
