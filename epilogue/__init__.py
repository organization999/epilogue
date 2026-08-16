"""Public Python API for Epilogue.

Epilogue is a Python 3, batch-only observability library.  The package exposes
two complementary monitoring surfaces:

* :class:`BatchMonitor` records arbitrary JSON-serializable application data and
  persists it as append-only NDJSON for post-processing.
* :class:`StackMonitor` records an in-memory history of stack operations for the
  stack tracing/recovery demonstration.

Neither surface depends on UNI, C++ types, or any application-specific domain
model.
"""

from .batch   import BatchMonitor
from .monitor import StackMonitor

__all__ = [
    'BatchMonitor',
    'StackMonitor',
]
