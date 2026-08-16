from __future__ import annotations

import json
import unittest

from pathlib import Path
from tempfile import TemporaryDirectory

from epilogue.batch import BatchMonitor


class BatchMonitorTest(unittest.TestCase):

    def test_expression_data_is_persisted_without_domain_knowledge(self) -> None:
        with TemporaryDirectory() as directory:
            path: Path = Path(directory) / 'expressions.ndjson'
            monitor: BatchMonitor[dict[str, object]] = BatchMonitor(
                path,
                batch_size=2,
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

    def test_explicit_flush_persists_partial_batch(self) -> None:
        with TemporaryDirectory() as directory:
            path: Path = Path(directory) / 'partial.ndjson'
            monitor: BatchMonitor[int] = BatchMonitor(
                path,
                batch_size=8,
            )

            monitor.log('value.execute', 42)
            monitor.flush()

            self.assertEqual(0, monitor.pending())
            self.assertTrue(path.exists())

    def test_invalid_batch_size_is_rejected(self) -> None:
        with TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                BatchMonitor[int](
                    Path(directory) / 'invalid.ndjson',
                    batch_size=0,
                )


if __name__ == '__main__':
    unittest.main()
