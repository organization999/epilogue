from __future__ import annotations

from dataclasses import dataclass
from typing      import Generic, TypeVar

T = TypeVar('T')

@dataclass(frozen=True)
class StackSnapshot(Generic[T]):
    data : list[T]
    top  : int
    cap  : int
