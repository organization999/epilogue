"""Record expression-shaped data with the generic Epilogue monitor.

This example intentionally does not import UNI.  The dictionaries below merely
use the same Python data language that an embedding application could expose at
its Python boundary.  Epilogue treats every observation as opaque data.

Run from the repository root with::

    python examples/expression_observability.py

The example writes an append-only NDJSON ledger under ``tmp/epilogue``.
"""

from __future__ import annotations

import json

from pathlib import Path
from typing  import TypedDict

from epilogue import BatchMonitor


class TokenData(TypedDict):
    """Describe one application-defined token.

    Attributes:
        kind: Numeric token category selected by the embedding application.
        value: Numeric value associated with the token.
    """

    kind: int
    value: int


class ExpressionData(TypedDict):
    """Example expression observation schema.

    Attributes:
        version: Version of the producer's tokenization/data contract.
        tokens: Ordered token records describing the expression.
        literals: Literal payloads referenced by the token stream.

    Notes:
        This type belongs to the example application, not to Epilogue.
        Epilogue itself has no expression schema.
    """

    version: int
    tokens: list[TokenData]
    literals: list[float]


def make_expression(
    literal: float,
) -> ExpressionData:
    """Create one small expression-shaped observation.

    Args:
        literal: Literal value represented by the example expression.

    Returns:
        Application-owned dictionary suitable for JSON serialization.
    """
    return {
        'version': 2,
        'tokens': [
            {'kind': 0, 'value': 0},
        ],
        'literals': [
            literal,
        ],
    }


def main() -> int:
    """Write a small batch and print the resulting persisted records.

    Returns:
        Process exit status.  ``0`` indicates the example completed normally.
    """
    ledger: Path = (
        Path('tmp')
        / 'epilogue'
        / 'expression-observability.ndjson'
    )

    if ledger.exists():
        ledger.unlink()

    with BatchMonitor[ExpressionData](
        ledger,
        batch_size=2,
    ) as monitor:
        monitor.log(
            'expression.execute',
            make_expression(2.0),
        )

        print(
            f'pending after first observation: {monitor.pending()}'
        )

        monitor.log(
            'expression.execute',
            make_expression(3.0),
        )

        print(
            f'pending after automatic flush: {monitor.pending()}'
        )

        monitor.log_batch(
            'expression.execute',
            [
                make_expression(5.0),
                make_expression(8.0),
            ],
        )

    print(
        f'ledger: {ledger}'
    )

    with open(
        ledger,
        mode='r',
        encoding='utf-8',
    ) as source:
        for line in source:
            record: dict[str, object] = json.loads(
                line
            )

            print(
                json.dumps(
                    record,
                    indent=2,
                )
            )

    return 0


if __name__ == '__main__':
    raise SystemExit(
        main()
    )
