from __future__ import annotations

import argparse

from proofledger.domain.reconciliation import ReconciliationEngine
from proofledger.services.benchmark import ReconciliationBenchmark
from proofledger.services.workspace import DemoWorkspace


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(
        prog="proofledger",
        description="Reproduce ProofLedger demo evidence and evaluation.",
    )
    command.add_argument("--seed", type=int, default=2026)
    command.add_argument("--orders", type=int, default=600)
    command.add_argument("--settlement-size", type=int, default=50)
    command.add_argument(
        "operation",
        choices=["summary", "benchmark"],
        help="Output a workspace summary or benchmark as JSON.",
    )
    return command


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    workspace = DemoWorkspace(
        seed=args.seed,
        order_count=args.orders,
        settlement_size=args.settlement_size,
    )
    if args.operation == "summary":
        from pydantic_core import to_json

        print(to_json(workspace.overview(), indent=2).decode())
        return 0

    decisions = ReconciliationEngine().reconcile(workspace.dataset.records)
    report = ReconciliationBenchmark().evaluate(
        workspace.dataset.records,
        workspace.dataset.true_links,
        decisions,
    )
    print(report.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
