from __future__ import annotations

from typing import Generic, TypeVar

from ..snapshot import StackSnapshot

T = TypeVar('T')

class Stack(Generic[T]):

    def __init__(self, cap: int) -> None:
        self.__cap  : int            = cap
        self.__top  : int            = 0
        self.__data : list[T | None] = [None] * cap

    def push(self, element: T) -> None:
        if self.__top >= self.__cap:
            raise RuntimeError('Stack is full')
        self.__data[self.__top] = element
        self.__top += 1

    def peek(self) -> T | None:
        if 0 == self.__top:
            return None
        return self.__data[self.__top - 1]

    def pop(self) -> T | None:
        if 0 == self.__top:
            return None
        self.__top -= 1
        element: T | None = self.__data[self.__top]
        self.__data[self.__top] = None
        return element

    def empty(self) -> bool:
        return (0 == self.__top)

    def size(self) -> int:
        return self.__top

    def save(self) -> StackSnapshot[T | None]:
        active_data = list(self.__data[:self.__top])
        return StackSnapshot(
            data=active_data,
            top=self.__top,
            cap=self.__cap
        )

    def restore(self, snapshot: StackSnapshot[T | None]) -> None:
        self.__cap = snapshot.cap
        self.__top = snapshot.top
        self.__data = [None] * self.__cap
        for i, val in enumerate(snapshot.data):
            self.__data[i] = val
