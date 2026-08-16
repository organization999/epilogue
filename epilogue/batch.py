from __future__ import annotations

import json
import threading
import time

from pathlib import Path
from typing  import Generic, Iterable, TypeVar

T = TypeVar('T')


class BatchMonitor(Generic[T]):
    """Collect generic Python observations and persist them in batches.

    Epilogue deliberately treats ``observation`` as opaque Python data. The
    embedding application owns the schema and is responsible for providing
    values that can be serialized by :mod:`json`.
    """

    def __init__(
        self,
        path: str | Path,
        batch_size: int = 256,
    ) -> None:
        if batch_size <= 0:
            raise ValueError('batch_size must be greater than zero')

        self.__path: Path = Path(path)
        self.__batch_size: int = batch_size
        self.__entries: list[dict[str, object]] = []
        self.__sequence: int = 0
        self.__lock: threading.Lock = threading.Lock()

    @property
    def path(self) -> Path:
        """Return the append-only ledger destination."""
        return self.__path

    @property
    def batch_size(self) -> int:
        """Return the number of records that triggers an automatic flush."""
        return self.__batch_size

    def log(self, operation: str, observation: T) -> None:
        """Record one observation and flush when the batch is full."""
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
        """Record an iterable of observations using one operation name."""
        for observation in observations:
            self.log(operation, observation)

    def pending(self) -> int:
        """Return the number of records waiting for persistence."""
        with self.__lock:
            return len(self.__entries)

    def flush(self) -> None:
        """Persist the current batch as append-only newline-delimited JSON."""
        with self.__lock:
            self.__flush_locked()

    def close(self) -> None:
        """Flush pending observations."""
        self.flush()

    def __enter__(self) -> BatchMonitor[T]:
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:  # type: ignore[no-untyped-def]
        self.close()

    def __flush_locked(self) -> None:
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
