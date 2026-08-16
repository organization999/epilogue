from __future__ import annotations

from typing import Generic, TypeVar

from .snapshot import StackSnapshot
from .trace    import StackTrace

T = TypeVar('T')

class StackMonitor(Generic[T]):

    def __init__(self) -> None:
        self.__trace: StackTrace[T] = StackTrace[T]()

    def log(
        self,
        operation: str,
        argument: T | None,
        snapshot: StackSnapshot[T | None],
    ) -> None:
        self.__trace.log(
            operation,
            argument,
            snapshot,
        )

    def dump(self) -> str:
        return self.__trace.dump()
