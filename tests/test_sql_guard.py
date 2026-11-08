from data_trust.errors import DataTrustError
from data_trust.sql_guard import assert_single_select

import pytest


def test_select_is_allowed():
    assert assert_single_select("SELECT 1") == "SELECT 1"


def test_string_that_mentions_drop_is_allowed():
    statement = assert_single_select("SELECT 'drop table' AS label")
    assert statement.startswith("SELECT")


def test_comment_that_mentions_drop_is_allowed():
    assert assert_single_select("SELECT 1 -- drop table").startswith("SELECT")


def test_drop_is_rejected():
    with pytest.raises(DataTrustError):
        assert_single_select("DROP TABLE orders")


def test_two_statements_are_rejected():
    with pytest.raises(DataTrustError):
        assert_single_select("SELECT 1; SELECT 2")
