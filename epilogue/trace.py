"""In-memory stack trace construction and rendering."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime    import datetime
from typing      import Generic, TypeVar

from .entry    import TraceEntry
from .snapshot import StackSnapshot

T = TypeVar('T')


@dataclass
class StackTrace(Generic[T]):
    """Maintain the ordered history of stack operations.

    Attributes:
        entries: Trace records in insertion order.

    Notes:
        ``StackTrace`` is intentionally an in-memory structure.  It is useful
        for human-readable debugging and recovery diagnostics.  Use
        :class:`epilogue.BatchMonitor` when observations need batch-oriented
        append-only persistence.
    """

    entries: list[TraceEntry[T]] = field(default_factory=list) # type: ignore

    def log(
        self,
        operation: str,
        argument: T | None,
        snapshot: StackSnapshot[T | None],
    ) -> None:
        """Append one timestamped trace entry.

        Args:
            operation: Human-readable operation name.
            argument: Optional value associated with the operation.
            snapshot: Stack state associated with the operation.

        Returns:
            None.

        Notes:
            The timestamp is captured with :func:`datetime.datetime.now` when
            this method is called.
        """
        self.entries.append(TraceEntry(
            timestamp=datetime.now(),
            operation=operation,
            argument=argument,
            snapshot=snapshot
        ))

    def dump(self) -> str:
        """Render the trace ledger.

        Returns:
            Multi-line string containing one operation line and one state line
            for every trace entry.  Timestamps are rendered to millisecond
            precision.

        Notes:
            Rendering does not mutate or clear the trace.
        """
        lines: list[str] = ['=== EPILOGUE STACK TRACE LEDGER ===']

        for idx, entry in enumerate(self.entries):
            ts: str = entry.timestamp.strftime('%H:%M:%S.%f')[:-3]
            arg_str: str = f' ({entry.argument})' if entry.argument is not None else ''
            lines.append(f'[{ts}] Step {idx}: {entry.operation}{arg_str}')
            lines.append(f'  └─ State: {entry.snapshot.data} (Size: {entry.snapshot.top}/{entry.snapshot.cap})')

        return '\n'.join(lines)
