"""Batch-oriented persistence for generic Epilogue observations.

This module contains :class:`BatchMonitor`, the generic persistence primitive
used by Epilogue integrations. A monitor accepts ordinary Python values,
attaches execution metadata, buffers records in memory, and writes complete
batches as newline-delimited JSON (NDJSON).

Epilogue intentionally does not define an observation schema. The embedding
application owns the payload type and semantic meaning. Consequently this
module can record UNI expression data, scheduler events, service telemetry, or
any other JSON-serializable Python value without importing those applications.
"""

from __future__ import annotations

import json
import threading
import time

from pathlib import Path
from typing import Callable, Generic, Iterable, TypeVar

from .cpu import SystemCPUUtilization

T = TypeVar('T')
CPUUtilizationSampler = Callable[[], float | None]


class BatchMonitor(Generic[T]):
    """Collect generic observations and persist them with sparse disk writes.

    Routine persistence has two triggers only:

    * the in-memory batch reaches ``batch_size``; or
    * :meth:`flush_if_cpu_low` observes host CPU utilization at or below
      ``low_cpu_threshold``.

    This keeps normal logging off the disk while the application is busy. A
    host integration may call :meth:`flush_if_cpu_low` frequently; Epilogue
    internally rate-limits CPU samples with ``cpu_check_interval`` and therefore
    does not turn a fast application polling loop into a fast disk-write loop.

    Explicit :meth:`flush` and :meth:`close` remain durability overrides for
    operator requests and process teardown. They are not part of the routine
    automatic flush policy.

    Args:
        path: Destination for the append-only NDJSON ledger. Parent directories
            are created lazily during the first flush.
        batch_size: Number of pending records that triggers an automatic flush.
            Must be greater than zero.
        low_cpu_threshold: Maximum host CPU utilization that permits an
            opportunistic partial-batch flush. ``20.0`` means a partial batch
            may be persisted when sampled utilization is at or below 20 percent.
        cpu_check_interval: Minimum seconds between host CPU samples used for
            opportunistic flushing. The default of five seconds bounds low-CPU
            disk opportunities even when the host calls
            :meth:`flush_if_cpu_low` much more frequently.
        cpu_sampler: Optional application/test supplied utilization callback.
            It must return a percentage in ``0.0..100.0`` or ``None`` when no
            sample is currently available. When omitted,
            :class:`SystemCPUUtilization` is used.

    Raises:
        ValueError: If ``batch_size`` or ``cpu_check_interval`` is not positive,
            or if ``low_cpu_threshold`` falls outside ``0.0..100.0``.

    Notes:
        Public mutation and inspection methods are synchronized with an internal
        :class:`threading.Lock`. One monitor can therefore be shared by multiple
        Python threads. The lock is process-local and does not provide
        inter-process file locking.

        Low-CPU persistence is deliberately *cooperative*. Epilogue owns the
        policy and CPU decision, while the embedding runtime supplies convenient
        scheduling points by calling :meth:`flush_if_cpu_low`. This avoids a
        permanent background thread inside every monitor instance.

        Timestamps use :func:`time.time_ns`. CPU-check scheduling uses
        :func:`time.monotonic_ns`, so wall-clock adjustments cannot cause a
        burst of utilization checks.
    """

    def __init__(
        self,
        path: str | Path,
        batch_size: int = 256,
        low_cpu_threshold: float = 20.0,
        cpu_check_interval: float = 5.0,
        cpu_sampler: CPUUtilizationSampler | None = None,
    ) -> None:
        """Initialize a sparse-write batch monitor.

        Construction does not touch the filesystem. The destination is created
        only after the batch fills, CPU utilization is sampled low enough, or an
        explicit durability method is invoked.
        """
        if batch_size <= 0:
            raise ValueError('batch_size must be greater than zero')

        if not (0.0 <= low_cpu_threshold <= 100.0):
            raise ValueError(
                'low_cpu_threshold must be between 0 and 100'
            )

        if cpu_check_interval <= 0.0:
            raise ValueError('cpu_check_interval must be greater than zero')

        system_cpu = SystemCPUUtilization()

        self.__path: Path = Path(path)
        self.__batch_size: int = batch_size
        self.__low_cpu_threshold: float = float(low_cpu_threshold)
        self.__cpu_check_interval_ns: int = max(
            1,
            int(cpu_check_interval * 1_000_000_000.0),
        )
        self.__cpu_sampler: CPUUtilizationSampler = (
            cpu_sampler
            if cpu_sampler is not None
            else system_cpu.sample
        )
        self.__entries: list[dict[str, object]] = []
        self.__sequence: int = 0
        self.__next_cpu_check_ns: int = 0
        self.__lock: threading.Lock = threading.Lock()

    @property
    def path(self) -> Path:
        """Return the configured append-only ledger destination."""
        return self.__path

    @property
    def batch_size(self) -> int:
        """Return the full-batch automatic flush threshold."""
        return self.__batch_size

    @property
    def low_cpu_threshold(self) -> float:
        """Return the utilization percentage permitting opportunistic flushes."""
        return self.__low_cpu_threshold

    @property
    def cpu_check_interval(self) -> float:
        """Return the minimum seconds between opportunistic CPU samples."""
        return (
            float(self.__cpu_check_interval_ns)
            / 1_000_000_000.0
        )

    def log(self, operation: str, observation: T) -> None:
        """Buffer one observation and persist only when the batch becomes full.

        Args:
            operation: Non-empty application-defined operation name.
            observation: Opaque JSON-serializable application payload.

        Notes:
            ``log`` intentionally does not perform a CPU utilization sample.
            CPU-aware partial persistence is separated into
            :meth:`flush_if_cpu_low`, allowing a runtime to place checks in its
            existing idle/maintenance loop without putting system calls on every
            logging operation.
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
        """Buffer an iterable of observations using one operation name."""
        for observation in observations:
            self.log(operation, observation)

    def pending(self) -> int:
        """Return the number of records still buffered in memory."""
        with self.__lock:
            return len(self.__entries)

    def flush_if_cpu_low(
        self,
        *,
        force_check: bool = False,
    ) -> bool:
        """Persist a partial batch only when sampled host CPU utilization is low.

        Args:
            force_check: Ignore the normal CPU sampling interval for this call.
                This forces a *CPU sample*, not a disk write. The batch is still
                persisted only if utilization is at or below
                ``low_cpu_threshold``.

        Returns:
            ``True`` when pending data was written to disk. ``False`` when the
            batch was empty, the CPU check was rate-limited, no utilization
            sample was available, or sampled utilization was above the threshold.

        Notes:
            CPU sampling is performed outside the monitor lock. The disk flush,
            when allowed, re-enters the lock and persists whatever entries are
            pending at that moment.
        """
        now: int = time.monotonic_ns()

        with self.__lock:
            if not self.__entries:
                return False

            if (
                (not force_check)
                and (now < self.__next_cpu_check_ns)
            ):
                return False

            self.__next_cpu_check_ns = (
                now
                + self.__cpu_check_interval_ns
            )

        utilization: float | None = self.__cpu_sampler()

        if utilization is None:
            return False

        utilization = min(
            100.0,
            max(
                0.0,
                float(utilization),
            ),
        )

        if utilization > self.__low_cpu_threshold:
            return False

        with self.__lock:
            if not self.__entries:
                return False

            self.__flush_locked()
            return True

    def flush(self) -> None:
        """Force persistence of all pending records.

        This method is an explicit durability override. Routine integrations
        should prefer full-batch flushing plus :meth:`flush_if_cpu_low`.
        """
        with self.__lock:
            self.__flush_locked()

    def close(self) -> None:
        """Force persistence of pending observations during monitor teardown."""
        self.flush()

    def __enter__(self) -> BatchMonitor[T]:
        """Enter a context-manager scope and return this monitor."""
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:  # type: ignore[no-untyped-def]
        """Force pending data to disk when leaving a context-manager scope."""
        self.close()

    def __flush_locked(self) -> None:
        """Encode and append the current batch while ``__lock`` is held."""
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
