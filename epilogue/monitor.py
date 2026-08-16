from __future__ import annotations

from .snapshot import StackSnapshot
from .trace    import StackTrace

class StackMonitor:

    def __init__(self) -> None:
        self.__trace: StackTrace[str] = StackTrace[str]()

    def log(self, operation: str, argument: str | None, snapshot: StackSnapshot[str | None]) -> None:
        self.__trace.log(operation, argument, snapshot)

    def dump(self) -> str:
        return self.__trace.dump()
