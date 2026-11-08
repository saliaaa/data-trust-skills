from pathlib import Path

import yaml

from data_trust.contract import validate_contract

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "examples" / "broken-revenue-demo" / "gross_item_revenue.contract.yaml"


def test_demo_contract_is_valid():
    report = validate_contract(yaml.safe_load(CONTRACT.read_text()))
    assert report["valid"] is True
    assert report["findings"] == []
    assert report["query_budget"] == {"used": 0, "limit": 0}


def test_missing_owner_and_tolerance_fail():
    document = yaml.safe_load(CONTRACT.read_text())
    del document["owner"]
    report = validate_contract(document)
    assert report["valid"] is False
    assert any("owner" in item["message"] for item in report["findings"])

    document = yaml.safe_load(CONTRACT.read_text())
    document["tolerance"] = {}
    report = validate_contract(document)
    assert any("tolerance" in item["message"] for item in report["findings"])


def test_bad_boundary_is_rejected_and_null_denominator_is_allowed():
    document = yaml.safe_load(CONTRACT.read_text())
    document["time"]["boundary"] = "closed"
    report = validate_contract(document)
    assert any("boundary" in item["message"] for item in report["findings"])

    document = yaml.safe_load(CONTRACT.read_text())
    document["denominator"] = None
    document["exclusions"] = []
    assert validate_contract(document)["valid"] is True
