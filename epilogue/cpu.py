"""Cross-platform CPU utilization sampling for Epilogue.

The sampler in this module intentionally relies only on Python's standard
library. Epilogue remains a pure-Python package and does not require psutil or
another native dependency merely to decide when an opportunistic disk flush is
appropriate.
"""

from __future__ import annotations

import ctypes
import os
import threading

from pathlib import Path


class SystemCPUUtilization:
    """Sample approximate host CPU utilization as a percentage.

    The sampler prefers platform-native cumulative CPU counters so successive
    samples can be converted into utilization over an interval.

    * Windows uses ``GetSystemTimes`` through :mod:`ctypes`.
    * Linux reads the aggregate counters from ``/proc/stat``.
    * Other platforms fall back to a one-minute load average normalized by the
      number of logical CPUs when :func:`os.getloadavg` is available.

    Notes:
        Instances are thread-safe. A sampler is intentionally stateful because
        Windows and Linux expose cumulative CPU time rather than an instantaneous
        utilization percentage.
    """

    def __init__(self) -> None:
        """Initialize an empty CPU sampling history."""
        self.__lock: threading.Lock = threading.Lock()
        self.__previous_idle: int | None = None
        self.__previous_total: int | None = None

    def sample(self) -> float | None:
        """Return host CPU utilization in the inclusive range ``0.0..100.0``.

        Returns:
            A utilization percentage, or ``None`` when the platform cannot be
            sampled or a second cumulative sample is still required.
        """
        with self.__lock:
            if os.name == 'nt':
                return self.__sample_windows()

            linux = self.__sample_linux()

            if linux is not None:
                return linux

            return self.__sample_load_average()

    def __sample_windows(self) -> float | None:
        """Sample Windows aggregate CPU counters with ``GetSystemTimes``."""

        class FILETIME(ctypes.Structure):
            _fields_ = [
                ('low', ctypes.c_uint32),
                ('high', ctypes.c_uint32),
            ]

        idle = FILETIME()
        kernel = FILETIME()
        user = FILETIME()

        get_system_times = ctypes.windll.kernel32.GetSystemTimes  # type: ignore[attr-defined]
        get_system_times.argtypes = [
            ctypes.POINTER(FILETIME),
            ctypes.POINTER(FILETIME),
            ctypes.POINTER(FILETIME),
        ]
        get_system_times.restype = ctypes.c_int

        if not get_system_times(
            ctypes.byref(idle),
            ctypes.byref(kernel),
            ctypes.byref(user),
        ):
            return None

        idle_ticks: int = self.__filetime_value(idle.low, idle.high)
        kernel_ticks: int = self.__filetime_value(kernel.low, kernel.high)
        user_ticks: int = self.__filetime_value(user.low, user.high)

        # Windows kernel time includes idle time.
        return self.__utilization_from_counters(
            idle_ticks,
            kernel_ticks + user_ticks,
        )

    def __sample_linux(self) -> float | None:
        """Sample Linux aggregate counters from ``/proc/stat`` when present."""
        stat: Path = Path('/proc/stat')

        if not stat.exists():
            return None

        try:
            line: str = stat.read_text(
                encoding='utf-8',
                errors='strict',
            ).splitlines()[0]
        except (OSError, IndexError, UnicodeError):
            return None

        fields: list[str] = line.split()

        if (not fields) or ('cpu' != fields[0]):
            return None

        try:
            counters: list[int] = [
                int(value)
                for value in fields[1:]
            ]
        except ValueError:
            return None

        if len(counters) < 4:
            return None

        idle_ticks: int = counters[3]

        if len(counters) > 4:
            idle_ticks += counters[4]

        return self.__utilization_from_counters(
            idle_ticks,
            sum(counters),
        )

    def __sample_load_average(self) -> float | None:
        """Approximate CPU pressure from normalized one-minute load average."""
        getloadavg = getattr(
            os,
            'getloadavg',
            None,
        )

        if getloadavg is None:
            return None

        try:
            one_minute, _, _ = getloadavg()
        except OSError:
            return None

        cpu_count: int = os.cpu_count() or 1

        return self.__clamp(
            (float(one_minute) / float(cpu_count)) * 100.0
        )

    def __utilization_from_counters(
        self,
        idle: int,
        total: int,
    ) -> float | None:
        """Convert cumulative idle/total counters into interval utilization."""
        previous_idle: int | None = self.__previous_idle
        previous_total: int | None = self.__previous_total

        self.__previous_idle = idle
        self.__previous_total = total

        if (previous_idle is None) or (previous_total is None):
            return None

        idle_delta: int = idle - previous_idle
        total_delta: int = total - previous_total

        if total_delta <= 0:
            return None

        busy_delta: int = total_delta - idle_delta

        return self.__clamp(
            (float(busy_delta) / float(total_delta)) * 100.0
        )

    @staticmethod
    def __filetime_value(
        low: int,
        high: int,
    ) -> int:
        """Combine a Windows ``FILETIME`` pair into one unsigned integer."""
        return (
            (int(high) << 32)
            | int(low)
        )

    @staticmethod
    def __clamp(value: float) -> float:
        """Clamp a percentage to the valid utilization range."""
        return min(
            100.0,
            max(
                0.0,
                value,
            ),
        )
