"""Batch-oriented persistence for generic Epilogue observations.

This module contains :class:`BatchMonitor`, the generic persistence primitive
used by Epilogue integrations.  A monitor accepts ordinary Python values,
attaches execution metadata, buffers records in memory, and writes complete
batches as newline-delimited JSON (NDJSON).

Epilogue intentionally does not define an observation schema.  The embedding
application owns the payload type and semantic meaning.  Consequently this
module can record UNI expression data, scheduler events, service telemetry, or
any other JSON-serializable Python value without importing those applications.
"""

from __future__ import annotations

import json
import threading
import time

from pathlib import Path
from typing  import Generic, Iterable, TypeVar

T = TypeVar('T')


class BatchMonitor(Generic[T]):
    """Collect generic Python observations and persist them in batches.

    ``BatchMonitor`` is the batch-only storage boundary for Epilogue.  Each call
    to :meth:`log` creates a record containing a monotonically increasing
    process-local sequence number, a nanosecond wall-clock timestamp, an
    application-defined operation name, and the opaque application observation.

    Records are retained in memory until ``batch_size`` records are pending or
    the caller explicitly invokes :meth:`flush` or :meth:`close`.  Persistence
    is append-only NDJSON: one complete JSON object is written per line.

    The observation type parameter ``T`` exists only for static typing.
    Epilogue does not inspect, transform, or otherwise interpret values of that
    type.  Values must only be serializable by :func:`json.dumps`.

    Args:
        path: Destination for the append-only NDJSON ledger.  Parent directories
            are created lazily during the first flush.
        batch_size: Maximum number of in-memory records before an automatic
            flush.  Must be greater than zero.

    Raises:
        ValueError: If ``batch_size`` is zero or negative.

    Notes:
        Public mutation and inspection methods are synchronized with an internal
        :class:`threading.Lock`.  A monitor may therefore be shared by multiple
        Python threads.  The lock protects monitor state; it does not provide
        inter-process locking for multiple processes writing the same file.

        Timestamps are captured with :func:`time.time_ns`, so ``timestamp_ns``
        represents wall-clock nanoseconds since the Unix epoch.  ``sequence`` is
        independent of wall-clock time and is monotonically increasing only for
        the lifetime of this monitor instance.

        Destructor-based durability is intentionally avoided.  Use
        :meth:`close`, :meth:`flush`, or the context-manager protocol when
        pending records must be persisted deterministically.

    Example:
        >>> from epilogue import BatchMonitor
        >>> monitor = BatchMonitor[dict[str, object]](
        ...     'tmp/epilogue/events.ndjson',
        ...     batch_size=2,
        ... )
        >>> monitor.log('expression.execute', {'version': 2})
        >>> monitor.pending()
        1
        >>> monitor.close()
    """

    def __init__(
        self,
        path: str | Path,
        batch_size: int = 256,
    ) -> None:
        """Initialize an append-only batch monitor.

        Args:
            path: File path receiving persisted NDJSON records.
            batch_size: Number of pending records that triggers an automatic
                flush.

        Raises:
            ValueError: If ``batch_size`` is less than or equal to zero.

        Notes:
            Construction does not touch the filesystem.  The destination parent
            directory and file are created only when a non-empty batch is
            flushed.
        """
        if batch_size <= 0:
            raise ValueError('batch_size must be greater than zero')

        self.__path: Path = Path(path)
        self.__batch_size: int = batch_size
        self.__entries: list[dict[str, object]] = []
        self.__sequence: int = 0
        self.__lock: threading.Lock = threading.Lock()

    @property
    def path(self) -> Path:
        """Return the configured append-only ledger destination.

        Returns:
            The :class:`pathlib.Path` supplied when the monitor was constructed.

        Notes:
            The path may not exist yet because Epilogue creates it lazily during
            the first non-empty flush.
        """
        return self.__path

    @property
    def batch_size(self) -> int:
        """Return the automatic-flush threshold.

        Returns:
            The positive number of pending records required to trigger an
            automatic flush.
        """
        return self.__batch_size

    def log(self, operation: str, observation: T) -> None:
        """Record one observation.

        The observation is wrapped with Epilogue metadata and appended to the
        current in-memory batch.  If the append reaches ``batch_size``, the
        complete batch is persisted before this method returns.

        Args:
            operation: Application-defined name describing what was observed.
                The value is stored verbatim in the ledger and must not be empty.
            observation: Opaque application payload.  Epilogue does not inspect
                its schema, but it must be JSON-serializable when the batch is
                flushed.

        Raises:
            ValueError: If ``operation`` is empty, or if automatic flushing
                encounters a non-finite float while JSON encoding.
            TypeError: If automatic flushing encounters a value unsupported by
                Python's JSON encoder.
            OSError: If automatic flushing cannot create or append to the ledger.

        Notes:
            Sequence numbers are assigned while holding the monitor lock, so the
            order recorded by one monitor is deterministic with respect to
            successful calls entering the critical section.
        """
        if not operation:
            raise ValueError('operation must not be empty')

        with self.__lock:
            self.__entries.append({
                'sequence': self.__sequence,
                'timestamp_ns': time.time_ns(),
                'operation': operation,
                'observation': observation,
            })

            self.__sequence += 1

            if len(self.__entries) >= self.__batch_size:
                self.__flush_locked()

    def log_batch(self, operation: str, observations: Iterable[T]) -> None:
        """Record an iterable of observations using one operation name.

        Args:
            operation: Application-defined operation stored on every generated
                record.
            observations: Iterable of opaque application payloads.

        Raises:
            ValueError: If ``operation`` is empty, or if a flush encounters a
                non-finite float.
            TypeError: If a flush encounters a non-JSON-serializable value.
            OSError: If a flush cannot create or append to the ledger.

        Notes:
            This method delegates each element to :meth:`log`.  Therefore normal
            batch thresholds still apply while the iterable is consumed; a large
            iterable can produce multiple persisted batches.
        """
        for observation in observations:
            self.log(operation, observation)

    def pending(self) -> int:
        """Return the number of records still buffered in memory.

        Returns:
            Count of records that have not yet been persisted by this monitor.
        """
        with self.__lock:
            return len(self.__entries)

    def flush(self) -> None:
        """Persist all pending records.

        Pending entries are JSON-encoded and appended to the configured ledger
        as one NDJSON line per record.  An empty flush is a no-op.

        Raises:
            ValueError: If an observation contains a non-finite float.  Epilogue
                uses ``allow_nan=False`` so persisted data remains strict JSON.
            TypeError: If a record contains a value unsupported by the standard
                JSON encoder.
            OSError: If the destination directory cannot be created or the
                ledger cannot be opened or written.

        Notes:
            Entries are cleared only after the append completes successfully.
            If encoding or I/O fails, the pending batch remains available for a
            later retry.
        """
        with self.__lock:
            self.__flush_locked()

    def close(self) -> None:
        """Flush pending observations as the monitor's durability boundary.

        Raises:
            ValueError: If pending data cannot be represented as strict JSON.
            TypeError: If pending data is not JSON-serializable.
            OSError: If pending data cannot be persisted.

        Notes:
            ``close()`` currently does not permanently disable the monitor; it
            is an explicit durability operation equivalent to :meth:`flush`.
        """
        self.flush()

    def __enter__(self) -> BatchMonitor[T]:
        """Enter a context-manager scope.

        Returns:
            This monitor instance.
        """
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:  # type: ignore[no-untyped-def]
        """Flush pending observations when leaving a context-manager scope.

        Args:
            exc_type: Exception type active at scope exit, if any.
            exc_value: Exception instance active at scope exit, if any.
            traceback: Traceback active at scope exit, if any.

        Notes:
            Exceptions raised inside the managed block are not suppressed.
            ``close()`` is still attempted while the scope exits.
        """
        self.close()

    def __flush_locked(self) -> None:
        """Encode and append the current batch while ``__lock`` is held.

        This helper centralizes the durable write path for both automatic and
        explicit flushing.  Callers must already own ``__lock``.

        Raises:
            ValueError: If strict JSON encoding rejects a non-finite float.
            TypeError: If JSON encoding encounters an unsupported value.
            OSError: If directory creation or file I/O fails.
        """
        if not self.__entries:
            return

        encoded: list[str] = [
            json.dumps(
                entry,
                ensure_ascii=False,
                allow_nan=False,
                separators=(',', ':'),
            )
            for entry in self.__entries
        ]

        self.__path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with open(
            self.__path,
            mode='a',
            encoding='utf-8',
            newline='\n',
        ) as ledger:
            ledger.write('\n'.join(encoded))
            ledger.write('\n')

        self.__entries.clear()
