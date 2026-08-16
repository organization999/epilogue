from __future__ import annotations

from dataclasses import dataclass
from datetime    import datetime
from typing      import Generic, TypeVar

from .snapshot import StackSnapshot

T = TypeVar('T')

@dataclass(frozen=True)
class TraceEntry(Generic[T]):
    timestamp : datetime
    operation : str
    argument  : T | None
    snapshot  : StackSnapshot[T | None]
