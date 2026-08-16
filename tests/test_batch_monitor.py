from __future__ import annotations

import json
import unittest

from pathlib import Path
from tempfile import TemporaryDirectory

from epilogue.batch import BatchMonitor


class BatchMonitorTest(unittest.TestCase):

    def test_full_batch_is_persisted_without_domain_knowledge(self) -> None:
        with TemporaryDirectory() as directory:
            path: Path = Path(directory) / 'expressions.ndjson'
            monitor: BatchMonitor[dict[str, object]] = BatchMonitor(
                path,
                batch_size=2,
                cpu_sampler=lambda: 100.0,
            )

            lhs: dict[str, object] = {
                'version': 2,
                'tokens': [
                    {'kind': 0, 'value': 0},
                ],
                'literals': [2.0],
            }

            rhs: dict[str, object] = {
                'version': 2,
                'tokens': [
                    {'kind': 0, 'value': 0},
                ],
                'literals': [3.0],
            }

            monitor.log('expression.execute', lhs)

            self.assertEqual(1, monitor.pending())
            self.assertFalse(path.exists())

            monitor.log('expression.execute', rhs)

            self.assertEqual(0, monitor.pending())

            rows: list[dict[str, object]] = [
                json.loads(line)
                for line in path.read_text(encoding='utf-8').splitlines()
            ]

            self.assertEqual(2, len(rows))
            self.assertEqual(lhs, rows[0]['observation'])
            self.assertEqual(rhs, rows[1]['observation'])
            self.assertEqual('expression.execute', rows[0]['operation'])
            self.assertEqual(0, rows[0]['sequence'])
            self.assertEqual(1, rows[1]['sequence'])

    def test_low_cpu_flushes_partial_batch(self) -> None:
        with TemporaryDirectory() as directory:
            path: Path = Path(directory) / 'low-cpu.ndjson'
            monitor: BatchMonitor[int] = BatchMonitor(
                path,
                batch_size=8,
                low_cpu_threshold=20.0,
                cpu_sampler=lambda: 5.0,
            )

            monitor.log('value.execute', 42)

            self.assertFalse(path.exists())
            self.assertTrue(
                monitor.flush_if_cpu_low(
                    force_check=True,
                )
            )
            self.assertEqual(0, monitor.pending())
            self.assertTrue(path.exists())

    def test_high_cpu_keeps_partial_batch_in_memory(self) -> None:
        with TemporaryDirectory() as directory:
            path: Path = Path(directory) / 'high-cpu.ndjson'
            monitor: BatchMonitor[int] = BatchMonitor(
                path,
                batch_size=8,
                low_cpu_threshold=20.0,
                cpu_sampler=lambda: 95.0,
            )

            monitor.log('value.execute', 42)

            self.assertFalse(
                monitor.flush_if_cpu_low(
                    force_check=True,
                )
            )
            self.assertEqual(1, monitor.pending())
            self.assertFalse(path.exists())

    def test_cpu_checks_are_rate_limited(self) -> None:
        with TemporaryDirectory() as directory:
            samples: list[float] = []

            def sample() -> float:
                samples.append(95.0)
                return 95.0

            monitor: BatchMonitor[int] = BatchMonitor(
                Path(directory) / 'rate.ndjson',
                batch_size=8,
                cpu_check_interval=60.0,
                cpu_sampler=sample,
            )

            monitor.log('value.execute', 42)

            self.assertFalse(monitor.flush_if_cpu_low())
            self.assertFalse(monitor.flush_if_cpu_low())
            self.assertEqual(1, len(samples))

    def test_explicit_flush_remains_durability_override(self) -> None:
        with TemporaryDirectory() as directory:
            path: Path = Path(directory) / 'partial.ndjson'
            monitor: BatchMonitor[int] = BatchMonitor(
                path,
                batch_size=8,
                cpu_sampler=lambda: 100.0,
            )

            monitor.log('value.execute', 42)
            monitor.flush()

            self.assertEqual(0, monitor.pending())
            self.assertTrue(path.exists())

    def test_invalid_configuration_is_rejected(self) -> None:
        with TemporaryDirectory() as directory:
            path: Path = Path(directory) / 'invalid.ndjson'

            with self.assertRaises(ValueError):
                BatchMonitor[int](
                    path,
                    batch_size=0,
                )

            with self.assertRaises(ValueError):
                BatchMonitor[int](
                    path,
                    low_cpu_threshold=101.0,
                )

            with self.assertRaises(ValueError):
                BatchMonitor[int](
                    path,
                    cpu_check_interval=0.0,
                )


if __name__ == '__main__':
    unittest.main()
