"""Validate a metric contract. This module does not query a warehouse."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

_AGGREGATIONS = {"sum", "count", "count_distinct", "min", "max", "avg"}
_BOUNDARIES = {"[start, end)", "[start, end]"}
_REQUIRED = (
    "metric",
    "version",
    "owner",
    "grain",
    "numerator",
    "denominator",
    "population",
    "exclusions",
    "dimensions",
    "time",
    "tolerance",
)
_OPTIONAL = {"description", "notes"}


def _text(value: Any, path: str, errors: list[str]) -> None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{path} must be a non-empty string")


def _number(value: Any, path: str, errors: list[str]) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        errors.append(f"{path} must be a number greater than or equal to 0")
        return
    try:
        parsed = Decimal(str(value))
    except InvalidOperation:
        errors.append(f"{path} must be a number greater than or equal to 0")
        return
    if parsed < 0:
        errors.append(f"{path} must be a number greater than or equal to 0")


def _component(value: Any, path: str, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append(f"{path} must be a mapping with expression, source, and aggregation")
        return
    _text(value.get("expression"), f"{path}.expression", errors)
    _text(value.get("source"), f"{path}.source", errors)
    if value.get("aggregation") not in _AGGREGATIONS:
        errors.append(f"{path}.aggregation must be one of: {', '.join(sorted(_AGGREGATIONS))}")
    extra = set(value) - {"expression", "source", "aggregation"}
    for key in sorted(extra):
        errors.append(f"{path}.{key} is not a contract field")


def validate_contract(document: Any) -> dict[str, Any]:
    """Return errors for a parsed contract. Does not run SQL."""
    errors: list[str] = []
    if not isinstance(document, dict):
        return _result(["contract must be a mapping"], [])
    unknown = set(document) - set(_REQUIRED) - _OPTIONAL
    for key in sorted(unknown):
        errors.append(f"{key} is not a contract field")
    for key in _REQUIRED:
        if key not in document:
            errors.append(f"{key} is required")

    if "metric" in document:
        _text(document.get("metric"), "metric", errors)
    if "version" in document and (isinstance(document.get("version"), bool) or not isinstance(document.get("version"), int) or document.get("version") < 1):
        errors.append("version must be an integer greater than or equal to 1")
    if "owner" in document:
        _text(document.get("owner"), "owner", errors)
    if "description" in document:
        _text(document.get("description"), "description", errors)
    if "notes" in document:
        _text(document.get("notes"), "notes", errors)

    grain = document.get("grain")
    if "grain" in document:
        if not isinstance(grain, list) or not grain or not all(isinstance(item, str) and item.strip() for item in grain):
            errors.append("grain must be a non-empty list of column names")

    if "numerator" in document:
        _component(document.get("numerator"), "numerator", errors)
    if "denominator" in document and document.get("denominator") is not None:
        _component(document.get("denominator"), "denominator", errors)

    population = document.get("population")
    if "population" in document:
        if not isinstance(population, dict):
            errors.append("population must be a mapping with description and predicate")
        else:
            _text(population.get("description"), "population.description", errors)
            _text(population.get("predicate"), "population.predicate", errors)
            for key in sorted(set(population) - {"description", "predicate"}):
                errors.append(f"population.{key} is not a contract field")

    exclusions = document.get("exclusions")
    if "exclusions" in document:
        if not isinstance(exclusions, list) or not all(isinstance(item, str) and item.strip() for item in exclusions):
            errors.append("exclusions must be a list of strings and may be empty")

    dimensions = document.get("dimensions")
    if "dimensions" in document:
        if not isinstance(dimensions, list) or not dimensions:
            errors.append("dimensions must be a non-empty list")
        else:
            for index, dimension in enumerate(dimensions):
                path = f"dimensions[{index}]"
                if not isinstance(dimension, dict):
                    errors.append(f"{path} must be a mapping with name and expression")
                    continue
                _text(dimension.get("name"), f"{path}.name", errors)
                _text(dimension.get("expression"), f"{path}.expression", errors)
                for key in sorted(set(dimension) - {"name", "expression"}):
                    errors.append(f"{path}.{key} is not a contract field")

    time = document.get("time")
    if "time" in document:
        if not isinstance(time, dict):
            errors.append("time must be a mapping")
        else:
            _text(time.get("timezone"), "time.timezone", errors)
            if time.get("boundary") not in _BOUNDARIES:
                errors.append("time.boundary must be '[start, end)' or '[start, end]'")
            if "stored_timezone" in time:
                _text(time.get("stored_timezone"), "time.stored_timezone", errors)
            if "fiscal_start_month" in time:
                month = time.get("fiscal_start_month")
                if isinstance(month, bool) or not isinstance(month, int) or not 1 <= month <= 12:
                    errors.append("time.fiscal_start_month must be an integer from 1 to 12")
            for key in sorted(set(time) - {"timezone", "boundary", "stored_timezone", "fiscal_start_month"}):
                errors.append(f"time.{key} is not a contract field")

    tolerance = document.get("tolerance")
    if "tolerance" in document:
        if not isinstance(tolerance, dict) or not ({"absolute", "relative"} & set(tolerance)):
            errors.append("tolerance needs absolute, relative, or both")
        elif isinstance(tolerance, dict):
            if "absolute" in tolerance:
                _number(tolerance.get("absolute"), "tolerance.absolute", errors)
            if "relative" in tolerance:
                _number(tolerance.get("relative"), "tolerance.relative", errors)
            for key in sorted(set(tolerance) - {"absolute", "relative"}):
                errors.append(f"tolerance.{key} is not a contract field")

    assumptions = [
        "Validation checks the contract file only. It does not query a warehouse and does not decide that a query implements the contract.",
        "A null denominator means the metric is not a ratio.",
        "An empty exclusions list means the population predicate is the whole filter.",
    ]
    return _result(errors, assumptions)


def _result(errors: list[str], assumptions: list[str]) -> dict[str, Any]:
    return {
        "skill": "define-metric-contract",
        "valid": not errors,
        "evidence": {"errors": errors, "error_count": len(errors)},
        "findings": [
            {
                "code": "contract_invalid",
                "severity": "fail",
                "message": error,
                "evidence": {"error": error},
            }
            for error in errors
        ],
        "assumptions": assumptions,
        "unknowns": [] if errors else ["Whether any query implements this contract is unknown until grain, time, and reconcile checks are run."],
        "query_budget": {"used": 0, "limit": 0},
    }
