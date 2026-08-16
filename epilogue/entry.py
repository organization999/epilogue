"""Immutable trace entry model used by stack observability."""

from __future__ import annotations

from dataclasses import dataclass
from datetime    import datetime
from typing      import Generic, TypeVar

from .snapshot import StackSnapshot

T = TypeVar('T')


@dataclass(frozen=True)
class TraceEntry(Generic[T]):
    """Describe one recorded stack operation.

    Attributes:
        timestamp: Wall-clock time at which the trace entry was created.
        operation: Application-defined operation name.
        argument: Optional value associated with the operation.
        snapshot: Immutable description of the stack state recorded for the
            operation.

    Notes:
        ``TraceEntry`` is frozen so a historical trace cannot be modified by
        assigning new field values after insertion.
    """

    timestamp : datetime
    operation : str
    argument  : T | None
    snapshot  : StackSnapshot[T | None]
