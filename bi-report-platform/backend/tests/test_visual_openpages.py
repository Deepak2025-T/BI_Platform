"""
The visual builder on an IBM OpenPages connection.

Its Query Service SQL is a different language rather than another dialect: COUNT is the only
function, it works on one object type and never beside a JOIN, there is no AS, and values cannot
travel as bound parameters. The builder therefore offers less here, and what it refuses it has to
refuse clearly - the person is dragging fields, not writing SQL, so "that isn't supported" has to
say what to do instead.
"""

import pytest

from app.datasources import DataSource
from app.visual_query import SpecError, compile_spec

FIELDS = [
    {"name": "Name", "type": "text", "values": []},
    {"name": "Resource ID", "type": "text", "values": []},
    {"name": "OPSS-Proc:Status", "type": "enum", "values": ["Open", "Closed"]},
    {"name": "OPSS-Proc:Domain", "type": "enum", "values": ["Finance", "IT"]},
    {"name": "OPSS-Proc:Start Date", "type": "date", "values": []},
]


class FakeClient:
    def type_fields(self, name):
        return FIELDS


def source():
    return DataSource(id=5, name="Timus demo", db_type="openpages", version="v1", client=FakeClient(),
                      tables=["openpages.SOXProcess", "openpages.Vendor"])


def test_counting_by_a_field_groups_the_way_openpages_wants():
    sql, params = compile_spec(source(), {
        "table": "openpages.SOXProcess",
        "dimensions": [{"column": "OPSS-Proc:Status"}],
        "measures": [{"column": "Resource ID", "agg": "count"}],
    })
    assert sql == ("SELECT [SOXProcess].[OPSS-Proc:Status], COUNT([SOXProcess].[Resource ID]) "
                   "FROM [SOXProcess] GROUP BY [SOXProcess].[OPSS-Proc:Status] "
                   "ORDER BY COUNT([SOXProcess].[Resource ID]) DESC")
    # No bound parameters: the Query Service has none.
    assert params == {}


def test_whatever_was_dragged_on_the_objects_are_counted():
    # COUNT in OpenPages counts objects; counting a particular field would mean something else
    # everywhere but here, so the resource id is what is counted.
    sql, _ = compile_spec(source(), {
        "table": "openpages.SOXProcess",
        "dimensions": [{"column": "OPSS-Proc:Domain"}],
        "measures": [{"column": "Name", "agg": "count"}],
    })
    assert "COUNT([SOXProcess].[Resource ID])" in sql
    assert "COUNT([SOXProcess].[Name])" not in sql


def test_a_list_with_no_number_is_left_ungrouped():
    sql, _ = compile_spec(source(), {
        "table": "openpages.SOXProcess",
        "dimensions": [{"column": "Name"}, {"column": "OPSS-Proc:Status"}],
    })
    assert sql == "SELECT [SOXProcess].[Name], [SOXProcess].[OPSS-Proc:Status] FROM [SOXProcess]"
    assert "GROUP BY" not in sql


def test_filters_are_written_in_and_quoted():
    sql, params = compile_spec(source(), {
        "table": "openpages.SOXProcess",
        "dimensions": [{"column": "OPSS-Proc:Domain"}],
        "measures": [{"agg": "count", "column": "Resource ID"}],
        "filters": [{"column": "OPSS-Proc:Status", "op": "in", "values": ["Open", "Closed"]},
                    {"column": "Name", "op": "contains", "value": "pay"}],
    })
    assert "[SOXProcess].[OPSS-Proc:Status] IN ('Open', 'Closed')" in sql
    assert "[SOXProcess].[Name] LIKE '%pay%'" in sql
    assert params == {}


def test_a_quote_in_a_filter_value_cannot_end_the_string():
    sql, _ = compile_spec(source(), {
        "table": "openpages.SOXProcess",
        "dimensions": [{"column": "Name"}],
        "filters": [{"column": "Name", "op": "=", "value": "O'Brien"}],
    })
    assert "'O''Brien'" in sql


def test_is_null_needs_no_value():
    sql, _ = compile_spec(source(), {
        "table": "openpages.SOXProcess",
        "dimensions": [{"column": "Name"}],
        "filters": [{"column": "OPSS-Proc:Status", "op": "is_null"}],
    })
    assert "[SOXProcess].[OPSS-Proc:Status] IS NULL" in sql


def test_summing_says_to_count_instead():
    with pytest.raises(SpecError) as err:
        compile_spec(source(), {
            "table": "openpages.SOXProcess",
            "dimensions": [{"column": "OPSS-Proc:Status"}],
            "measures": [{"column": "Name", "agg": "sum"}],
        })
    assert "only count" in str(err.value) and "Change it to Count" in str(err.value)


def test_grouping_a_date_by_month_says_why_it_cannot():
    with pytest.raises(SpecError) as err:
        compile_spec(source(), {
            "table": "openpages.SOXProcess",
            "dimensions": [{"column": "OPSS-Proc:Start Date", "bucket": "month"}],
            "measures": [{"agg": "count", "column": "Resource ID"}],
        })
    assert "no date functions" in str(err.value)


def test_a_joined_table_says_openpages_reads_one_type():
    with pytest.raises(SpecError) as err:
        compile_spec(source(), {
            "table": "openpages.SOXProcess",
            "joins": [{"table": "openpages.Vendor", "type": "left", "on": []}],
            "dimensions": [{"column": "Name"}],
        })
    assert "one object type at a time" in str(err.value)


def test_two_numbers_say_to_keep_one():
    with pytest.raises(SpecError) as err:
        compile_spec(source(), {
            "table": "openpages.SOXProcess",
            "dimensions": [{"column": "OPSS-Proc:Status"}],
            "measures": [{"agg": "count", "column": "Resource ID"},
                         {"agg": "count_distinct", "column": "Name"}],
        })
    assert "one number" in str(err.value)


def test_a_field_that_is_not_on_the_type_is_refused():
    with pytest.raises(SpecError) as err:
        compile_spec(source(), {
            "table": "openpages.SOXProcess",
            "dimensions": [{"column": "OPSS-Proc:Nonsense"}],
        })
    assert "no column called" in str(err.value)


def test_a_type_that_was_not_shared_is_refused():
    with pytest.raises(SpecError) as err:
        compile_spec(source(), {"table": "openpages.Policy", "dimensions": [{"column": "Name"}]})
    assert "isn't one of the tables shared" in str(err.value)


def test_ordering_by_the_count_column_the_results_come_back_with():
    # There is no AS, so a count arrives named "Count_Resource ID"; ordering by that name has to
    # become the count expression itself.
    sql, _ = compile_spec(source(), {
        "table": "openpages.SOXProcess",
        "dimensions": [{"column": "OPSS-Proc:Status"}],
        "measures": [{"agg": "count", "column": "Resource ID"}],
        "order": [{"ref": "Count_Resource ID", "dir": "asc"}],
    })
    assert sql.endswith("ORDER BY COUNT([SOXProcess].[Resource ID]) ASC")


def test_the_sql_it_writes_passes_the_openpages_guard():
    # Whatever the builder produces still has to survive the same check as model-written SQL.
    from app.connections.openpages import check_sql
    sql, _ = compile_spec(source(), {
        "table": "openpages.SOXProcess",
        "dimensions": [{"column": "OPSS-Proc:Status"}],
        "measures": [{"agg": "count", "column": "Resource ID"}],
        "filters": [{"column": "OPSS-Proc:Domain", "op": "=", "value": "Finance"}],
    })
    assert check_sql(sql, {"openpages.soxprocess"})
