"""Fixed-capacity Python stack used by the Epilogue trace demonstration."""

from __future__ import annotations

from typing import Generic, TypeVar

from ..snapshot import StackSnapshot

T = TypeVar('T')


class Stack(Generic[T]):
    """Store a bounded sequence of values with snapshot/restore support.

    Args:
        cap: Maximum number of active values.

    Notes:
        This collection is intentionally small and direct because its primary
        role is demonstrating Epilogue stack tracing and recovery behavior.
    """

    def __init__(self, cap: int) -> None:
        """Initialize an empty fixed-capacity stack.

        Args:
            cap: Number of slots allocated for the stack.
        """
        self.__cap  : int            = cap
        self.__top  : int            = 0
        self.__data : list[T | None] = [None] * cap

    def push(self, element: T) -> None:
        """Push one value onto the stack.

        Args:
            element: Value placed at the current top position.

        Raises:
            RuntimeError: If the stack is already at capacity.
        """
        if self.__top >= self.__cap:
            raise RuntimeError('Stack is full')
        self.__data[self.__top] = element
        self.__top += 1

    def peek(self) -> T | None:
        """Return the top value without removing it.

        Returns:
            Current top value, or ``None`` when the stack is empty.
        """
        if 0 == self.__top:
            return None
        return self.__data[self.__top - 1]

    def pop(self) -> T | None:
        """Remove and return the top value.

        Returns:
            Removed value, or ``None`` when the stack is empty.
        """
        if 0 == self.__top:
            return None
        self.__top -= 1
        element: T | None = self.__data[self.__top]
        self.__data[self.__top] = None
        return element

    def empty(self) -> bool:
        """Report whether the stack contains no active values.

        Returns:
            ``True`` when the stack size is zero; otherwise ``False``.
        """
        return (0 == self.__top)

    def size(self) -> int:
        """Return the number of active stack values.

        Returns:
            Logical stack size.
        """
        return self.__top

    def save(self) -> StackSnapshot[T | None]:
        """Capture the active stack state.

        Returns:
            Snapshot containing a copy of the active values, current size, and
            capacity.

        Notes:
            Only active positions are copied.  Unused capacity slots are not
            included in ``snapshot.data``.
        """
        active_data: list[T | None] = list(self.__data[:self.__top])
        return StackSnapshot(
            data=active_data,
            top=self.__top,
            cap=self.__cap
        )

    def restore(self, snapshot: StackSnapshot[T | None]) -> None:
        """Replace this stack with a previously captured state.

        Args:
            snapshot: Snapshot whose capacity, logical top, and active elements
                become the new stack state.

        Returns:
            None.
        """
        self.__cap = snapshot.cap
        self.__top = snapshot.top
        self.__data = [None] * self.__cap
        for i, val in enumerate(snapshot.data):
            self.__data[i] = val
