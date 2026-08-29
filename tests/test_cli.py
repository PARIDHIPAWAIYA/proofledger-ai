import json

from proofledger.cli import main


def test_summary_cli_prints_reproducible_json(capsys) -> None:
    result = main(
        [
            "--seed",
            "11",
            "--orders",
            "40",
            "--settlement-size",
            "20",
            "summary",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert result == 0
    assert payload["dataset_id"] == "synthetic_11_40"
    assert payload["settlement_count"] == 2
