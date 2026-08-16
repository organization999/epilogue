from __future__ import annotations

from dataclasses import dataclass, field
from datetime    import datetime
from typing      import Generic, TypeVar

from .entry    import TraceEntry
from .snapshot import StackSnapshot

T = TypeVar('T')

@dataclass
class StackTrace(Generic[T]):
    entries: list[TraceEntry[T]] = field(default_factory=list) # type: ignore

    def log(self, operation: str, argument: T | None, snapshot: StackSnapshot[T | None]) -> None:
        self.entries.append(TraceEntry(
            timestamp=datetime.now(),
            operation=operation,
            argument=argument,
            snapshot=snapshot
        ))

    def dump(self) -> str:
        lines = ["=== EPILOGUE STACK TRACE LEDGER ==="]
        for idx, entry in enumerate(self.entries):
            ts = entry.timestamp.strftime("%H:%M:%S.%f")[:-3]
            arg_str = f" ({entry.argument})" if entry.argument is not None else ""
            lines.append(f"[{ts}] Step {idx}: {entry.operation}{arg_str}")
            lines.append(f"  └─ State: {entry.snapshot.data} (Size: {entry.snapshot.top}/{entry.snapshot.cap})")
        return "\n".join(lines)
