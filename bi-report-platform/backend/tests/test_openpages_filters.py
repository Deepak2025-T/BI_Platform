"""
What a dashboard filter turns into on an OpenPages connection.

A whole report came back as "columnReference cannot be null. OP-60002: The query failed to be
transformed into SQL" the moment one filter was set - every chart on it, including charts that
share no field with the filter. The Query Service's SQL is a small grammar, and what we added to
the WHERE was outside it. These tests pin the shape of what we send.
"""

import pytest

from app import dashboard_filters
from app.datasources import DataSource


@pytest.fixture
def source(monkeypatch) -> DataSource:
    """An OpenPages connection with nothing behind it: these tests are about the SQL we write."""
    # The label-to-stored-value swap talks to OpenPages, and has its own tests.
    monkeypatch.setattr(dashboard_filters, "openpages_stored",
                        lambda source, type_name, field, value: value)
    return DataSource(id=7, name="GRC", db_type="openpages", version="v1",
                      tables=["openpages.Audit Plan Item"])


SQL = ("SELECT [Audit Plan Item].[IAM-PlanItem-FG:Status], COUNT([Audit Plan Item].[Resource ID]) "
       "FROM [Audit Plan Item] GROUP BY [Audit Plan Item].[IAM-PlanItem-FG:Status]")


def _filter(columns: dict, kind: str = "category", fid: str = "f1") -> dict:
    return {"id": fid, "label": "Risk level", "kind": kind, "columns": columns}


def _mapped(column="IAM-PlanItem-FG:RskLvl"):
    return {"w1": {"table": "openpages.Audit Plan Item", "column": column}}


def test_one_value_is_a_plain_comparison(source):
    sql, params, applied, skipped = dashboard_filters.apply(
        SQL, source, [_filter(_mapped())], {"f1": {"values": ["High"]}}, "w1")
    assert "WHERE [Audit Plan Item].[IAM-PlanItem-FG:RskLvl] = 'High' GROUP BY" in sql
    assert applied == ["f1"] and not skipped and params == {}


def test_several_values_are_one_IN_not_a_chain_of_ORs(source):
    """A chain of ORs has to be bracketed to mean what it says, and a bracketed predicate is what
    the Query Service refuses. IN is the form its own documentation gives."""
    sql, _, applied, _ = dashboard_filters.apply(
        SQL, source, [_filter(_mapped())], {"f1": {"values": ["High", "Medium"]}}, "w1")
    assert "WHERE [Audit Plan Item].[IAM-PlanItem-FG:RskLvl] IN ('High', 'Medium') GROUP BY" in sql
    assert " OR " not in sql and applied == ["f1"]


def test_nothing_we_add_is_wrapped_in_brackets(source):
    """The failure this all came from: every chart on a filtered report refused at once."""
    sql, _, _, _ = dashboard_filters.apply(
        SQL, source, [_filter(_mapped())], {"f1": {"values": ["High"]}}, "w1")
    assert "WHERE (" not in sql


def test_two_filters_are_joined_with_and(source):
    filters = [_filter(_mapped()), _filter({"w1": {"table": "openpages.Audit Plan Item",
                                                   "column": "IAM-PlanItem-FG:Status"}}, fid="f2")]
    values = {"f1": {"values": ["High"]}, "f2": {"values": ["Planned"]}}
    sql, _, applied, _ = dashboard_filters.apply(SQL, source, filters, values, "w1")
    assert ("WHERE [Audit Plan Item].[IAM-PlanItem-FG:RskLvl] = 'High' "
            "AND [Audit Plan Item].[IAM-PlanItem-FG:Status] = 'Planned' GROUP BY") in sql
    assert applied == ["f1", "f2"]


def test_a_date_filter_is_two_comparisons_and_no_brackets(source):
    f = _filter({"w1": {"table": "openpages.Audit Plan Item",
                        "column": "IAM-PlanItem-FG:PlndStrt"}}, kind="date")
    sql, _, applied, _ = dashboard_filters.apply(
        SQL, source, [f], {"f1": {"date_from": "2024-01-01", "date_to": "2024-03-31"}}, "w1")
    assert ("WHERE [Audit Plan Item].[IAM-PlanItem-FG:PlndStrt] >= '2024-01-01' "
            "AND [Audit Plan Item].[IAM-PlanItem-FG:PlndStrt] < '2024-04-01' GROUP BY") in sql
    assert applied == ["f1"] and "WHERE (" not in sql


# ---------- Filters that cannot be applied are left off, never written half-way ----------

@pytest.mark.parametrize("column", [None, "", "   "])
def test_a_filter_with_no_field_for_this_chart_is_skipped(source, column):
    """[Type].[] is literally what "columnReference cannot be null" means, and a saved report
    holds a missing field as None as readily as an empty string."""
    sql, _, applied, skipped = dashboard_filters.apply(
        SQL, source, [_filter(_mapped(column))], {"f1": {"values": ["High"]}}, "w1")
    assert sql == SQL, "the query goes out exactly as it was saved"
    assert applied == [] and skipped == ["f1"]


def test_a_filter_mapped_to_another_object_type_is_skipped(source):
    other = {"w1": {"table": "openpages.SOXIssue", "column": "OPSS-Iss:Status"}}
    sql, _, applied, skipped = dashboard_filters.apply(
        SQL, source, [_filter(other)], {"f1": {"values": ["Open"]}}, "w1")
    assert sql == SQL and applied == [] and skipped == ["f1"]


def test_a_filter_this_chart_was_never_mapped_for_is_skipped(source):
    sql, _, applied, skipped = dashboard_filters.apply(
        SQL, source, [_filter(_mapped())], {"f1": {"values": ["High"]}}, "w2")
    assert sql == SQL and applied == [] and skipped == ["f1"]


def test_a_value_with_a_quote_in_it_is_still_one_literal(source):
    sql, _, applied, _ = dashboard_filters.apply(
        SQL, source, [_filter(_mapped())], {"f1": {"values": ["O'Neil"]}}, "w1")
    assert "= 'O''Neil'" in sql and applied == ["f1"]


def test_a_chart_error_carries_what_it_means(monkeypatch):
    """"OP-60002: The query failed to be transformed into SQL" in a red box tells the person
    reading the report nothing they can do. Where the code is one we know, the message says so."""
    from app import report_data
    from app.datasources import QueryFailed

    src = DataSource(id=7, name="GRC", db_type="openpages", version="v1", tables=["openpages.T"])

    def boom(*args, **kwargs):
        raise QueryFailed("OpenPages returned HTTP 400: Bad Request - columnReference cannot be "
                          "null. OP-60002: The query failed to be transformed into SQL")

    monkeypatch.setattr(report_data, "run_sql", boom)
    config = {"widgets": [{"id": "w1", "sql": "SELECT [T].[A] FROM [T]", "chart": {"type": "bar"}}]}
    out = report_data.run_widgets(config, src, {})
    assert out[0]["ok"] is False
    assert "columnReference cannot be null" in out[0]["error"], "the original is still there"
    assert "clear the filter" in out[0]["error"], "and now says what to do about it"
