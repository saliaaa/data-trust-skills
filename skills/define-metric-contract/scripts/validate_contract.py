"""Validate a metric contract file. Does not query a warehouse."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from data_trust.contract import validate_contract
from data_trust.errors import DataTrustError
from data_trust.scripting import emit, fail


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a metric contract YAML file.")
    parser.add_argument("--contract", required=True)
    args = parser.parse_args(argv)
    try:
        path = Path(args.contract)
        if not path.is_file():
            raise DataTrustError(f"contract file does not exist: {path}")
        document = yaml.safe_load(path.read_text())
        return emit(validate_contract(document))
    except (DataTrustError, OSError, yaml.YAMLError) as exc:
        return fail(exc)


if __name__ == "__main__":
    raise SystemExit(main())
