"""Small SQL lint used by the demo.

This is not a substitute for a SQL linter. It only checks the three rules
the demo claims to pass.
"""

from __future__ import annotations

import re

from data_trust.sql_guard import strip_comments


def lint_grouped_select(sql: str) -> list[str]:
    scanned = strip_comments(sql)
    issues: list[str] = []
    if re.search(r"(?is)\bselect\s+\*", scanned):
        issues.append("SELECT * is present")
    if re.search(r"(?is)\bcross\s+join\b", scanned):
        issues.append("CROSS JOIN is present")
    if not re.search(r"(?is)\bgroup\s+by\b", scanned):
        issues.append("GROUP BY is absent")
    return issues
