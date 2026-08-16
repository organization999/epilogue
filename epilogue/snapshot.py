"""Immutable stack snapshot data model."""

from __future__ import annotations

from dataclasses import dataclass
from typing      import Generic, TypeVar

T = TypeVar('T')


@dataclass(frozen=True)
class StackSnapshot(Generic[T]):
    """Capture the logical state of a stack at one point in time.

    Attributes:
        data: Copy of the active stack elements in bottom-to-top order.
        top: Logical number of occupied positions in the source stack.
        cap: Capacity of the source stack when the snapshot was captured.

    Notes:
        The dataclass is frozen, which prevents reassignment of its fields.
        ``data`` is still a normal Python list and can technically be mutated by
        a caller; stack implementations should therefore treat snapshots as
        value objects and avoid sharing mutable backing storage.
    """

    data : list[T]
    top  : int
    cap  : int
