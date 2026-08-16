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

## Examples

A complete generic expression-data example is available at
`examples/expression_observability.py`. It deliberately does **not** import UNI;
it defines an application-owned `TypedDict`, records several observations, shows
automatic batch flushing, then reads the generated NDJSON back.

Run it from the repository root:

```text
python examples/expression_observability.py
```

The original stack tracing/recovery demonstration remains available with:

```text
python -m epilogue
```

These examples demonstrate the two separate Epilogue surfaces:

- `BatchMonitor[T]` is the generic batch persistence API used by integrations.
- `StackMonitor[T]` is an in-memory trace facade for stack state diagnostics.

## Batch behavior

Records remain in memory until the configured batch size is reached or `flush()`
/ `close()` is called. Each persisted line contains:

- `sequence`: process-local monotonically increasing record number.
- `timestamp_ns`: wall-clock timestamp in nanoseconds since the Unix epoch.
- `operation`: the application-supplied operation name.
- `observation`: the application-supplied Python value.

The ledger is append-only NDJSON so post-processing can stream records without
loading the complete run into memory.

`BatchMonitor` uses strict JSON encoding (`allow_nan=False`). Invalid JSON values,
unsupported object types, and filesystem errors are surfaced to the caller
rather than being silently discarded. Pending records are cleared only after a
successful append.

## Threading and lifecycle

A `BatchMonitor` protects its in-process buffer, sequence number, and flush path
with a Python lock, so multiple Python threads may share one monitor. This is
thread synchronization, not inter-process file locking; separate processes
should not assume coordinated writes to the same ledger.

Use `flush()`, `close()`, or the context-manager protocol as the explicit
durability boundary:

```python
with BatchMonitor[dict[str, object]](
    'path/to/ledger.ndjson',
) as monitor:
    monitor.log(
        'example.execute',
        {'value': 42},
    )
```

The context manager flushes pending records when its scope exits and does not
suppress exceptions from the managed block.

## Storage ownership

Epilogue accepts a destination path from the embedding application. It uses
normal Python filesystem APIs, so a host application may route those calls
through its own filesystem layer. UNI, for example, can place the ledger under
its LFS `/var/log/epilogue` hierarchy without adding LFS knowledge to Epilogue.

## Python only

Epilogue has no native C++ API and no pybind11 dependency. Native applications
that want to use Epilogue should expose their observation data at the Python
boundary and let Python own batching and persistence.

## API documentation

The Python sources use pydoc-compatible docstrings throughout the public API.
You can inspect them directly from a Python environment:

```text
python -m pydoc epilogue
python -m pydoc epilogue.batch
python -m pydoc epilogue.monitor
python -m pydoc epilogue.trace
```
