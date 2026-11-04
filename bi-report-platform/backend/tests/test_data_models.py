"""The OpenPages object models: reading the shipped namespaces, and serving them over the API."""

import pytest

from app import openpages_model as om
from app.datasources import DataSource, SourceError, narrow


def test_every_shipped_namespace_is_read():
    # One model per namespace in the reporting framework file, each with entities to show.
    assert len(om.MODELS) >= 16
    assert all(m.entities for m in om.MODELS)
    keys = {m.key for m in om.MODELS}
    assert "operational_risk_and_control/sox1" in keys
    assert "assurance_and_testing/aud1" in keys


def test_a_model_knows_its_solution_and_namespace():
    m = om.get("operational_risk_and_control/sox1")
    assert m.solution == "Operational Risk and Control"
    assert m.namespace == "SOX1"
    assert m.name == "Operational Risk and Control — SOX1"
    assert om.get("model_risk_and_data_privacy/default").is_default is True


def test_the_key_is_not_case_sensitive():
    assert om.get("Operational_Risk_and_Control/SOX1") is om.get("operational_risk_and_control/sox1")
    assert om.get("no/such/model") is None
    assert om.get(None) is None


def test_relationships_are_parent_to_child():
    m = om.get("operational_risk_and_control/sox1")
    pairs = {(r.parent, r.child) for r in m.relationships}
    assert ("SOXRisk", "SOXControl") in pairs
    assert ("SOXControl", "SOXTest") in pairs
    assert "SOXTest" in om.children_of(m, "SOXControl")
    assert om.parents_of(m, "SOXTest") == ["SOXControl"]


def test_a_type_that_nests_under_itself_is_kept_but_not_treated_as_a_parent():
    # SOXBusEntity|SOXBusEntity: business entities form a tree. It is a real relationship, but it
    # must not make the type its own parent, or nothing would ever come out as a root.
    m = om.get("operational_risk_and_control/sox1")
    assert any(r.is_self and r.parent == "SOXBusEntity" for r in m.relationships)
    assert om.parents_of(m, "SOXBusEntity") == []
    assert om.roots(m) == ["SOXBusEntity"]


def test_depth_follows_the_hierarchy():
    depth = om.depth_of(om.get("operational_risk_and_control/sox1"))
    assert depth["SOXBusEntity"] == 0
    assert depth["SOXProcess"] == 1
    assert depth["SOXRisk"] < depth["SOXControl"] < depth["SOXTest"] < depth["SOXTestResult"]


def test_every_model_lays_out_without_looping_forever():
    # Some namespaces relate a type back to one above it. Laying out must still finish.
    for m in om.MODELS:
        depth = om.depth_of(m)
        assert set(depth) == set(m.entities)
        assert max(depth.values()) <= len(m.entities)


def test_an_entity_with_no_edges_is_still_part_of_the_model():
    # "WKRegEvent" is named on its own, with no "|": a type the namespace uses but hangs nowhere.
    m = om.get("operational_risk_and_control/default")
    assert "WKRegEvent" in m.entities
    assert om.parents_of(m, "WKRegEvent") == []


def test_join_hints_are_written_as_openpages_sql():
    hints = om.join_hints(om.get("operational_risk_and_control/sox1"))
    assert "FROM [SOXRisk] JOIN [SOXControl] ON PARENT([SOXRisk])" in hints
    assert "nests under itself" in hints


# ---------- narrowing a source to a model ----------

def op_source(tables):
    return DataSource(id=7, name="OP", db_type="openpages", tables=tables, version="v1")


def test_narrowing_keeps_only_the_models_object_types():
    source = op_source(["openpages.SOXRisk", "openpages.SOXControl", "openpages.Vendor"])
    narrowed = narrow(source, "operational_risk_and_control/sox1")
    assert narrowed.tables == ["openpages.SOXRisk", "openpages.SOXControl"]
    # The SQL guard works off this set, so a type outside the model is simply not available.
    assert "openpages.vendor" not in narrowed.allowed
    assert narrowed.options["data_model"] == "operational_risk_and_control/sox1"


def test_narrowing_leaves_the_original_source_alone():
    source = op_source(["openpages.SOXRisk", "openpages.Vendor"])
    narrow(source, "operational_risk_and_control/sox1")
    assert source.tables == ["openpages.SOXRisk", "openpages.Vendor"]
    assert "data_model" not in source.options


def test_no_model_or_a_plain_database_is_left_as_it_was():
    source = op_source(["openpages.SOXRisk"])
    assert narrow(source, None) is source
    assert narrow(source, "") is source
    sql = DataSource(id=2, name="Warehouse", db_type="postgresql", tables=["public.sales"], version="v1")
    assert narrow(sql, "operational_risk_and_control/sox1") is sql


def test_a_model_sharing_no_types_says_so_rather_than_querying_nothing():
    source = op_source(["openpages.Vendor"])
    with pytest.raises(SourceError) as err:
        narrow(source, "assurance_and_testing/aud1")
    assert "Assurance and Testing" in str(err.value)


# ---------- the API ----------

def test_the_models_are_listed(client, user):
    res = client.get("/api/data-models", headers=user)
    assert res.status_code == 200
    rows = res.json()
    one = next(r for r in rows if r["key"] == "operational_risk_and_control/sox1")
    assert one["namespace"] == "SOX1"
    assert one["entity_count"] > 0 and one["relationship_count"] > 0


def test_one_model_gives_its_entities_and_relationships(client, user):
    res = client.get("/api/data-models/operational_risk_and_control/sox1", headers=user)
    assert res.status_code == 200
    body = res.json()
    assert body["connection"] is None and body["live"] is False
    names = [e["name"] for e in body["entities"]]
    assert "SOXBusEntity" in names and "SOXTestResult" in names
    root = next(e for e in body["entities"] if e["name"] == "SOXBusEntity")
    assert root["depth"] == 0 and root["self_nesting"] is True
    # Without a connection nothing is claimed about what exists or is shared.
    assert root["exists"] is None and root["shared"] is None
    assert {"parent": "SOXRisk", "child": "SOXControl", "self": False} in body["relationships"]


def test_an_unknown_model_is_not_found(client, user):
    assert client.get("/api/data-models/made/up", headers=user).status_code == 404


def test_refreshing_a_model_without_a_connection_still_answers(client, user):
    res = client.post("/api/data-models/operational_risk_and_control/sox1/refresh", headers=user)
    assert res.status_code == 200
    assert res.json()["key"] == "operational_risk_and_control/sox1"


def test_a_connection_that_cannot_be_read_still_draws_the_model(client, user):
    # A model has a shape whether or not a connection answers, so a missing or broken connection
    # is a note on the diagram rather than an error page.
    res = client.get("/api/data-models/operational_risk_and_control/sox1",
                     headers=user, params={"source_id": 999999})
    assert res.status_code == 200
    body = res.json()
    assert body["connection"] is None and body["live"] is False
    assert body["note"]
    assert len(body["entities"]) > 0


def test_signing_in_is_required(client):
    assert client.get("/api/data-models").status_code == 401
    assert client.get("/api/data-models/operational_risk_and_control/sox1").status_code == 401


def test_the_chosen_model_reaches_the_prompt(monkeypatch):
    """The point of picking a model: the query writer is told the types and how they join."""
    from app import datasources

    class FakeClient:
        def type_fields(self, name):
            return [{"name": "OPSS-Risk:Status", "type": "enum", "values": ["Open", "Closed"]}]

    source = DataSource(id=11, name="OP", db_type="openpages", version="v9", client=FakeClient(),
                        tables=["openpages.SOXBusEntity", "openpages.SOXRisk", "openpages.SOXControl",
                                "openpages.Vendor"])
    datasources.forget_schema()
    plain = datasources.describe(source)
    assert "SOXRisk" in plain and "nests under itself" not in plain

    datasources.forget_schema()
    text = datasources.describe(narrow(source, "operational_risk_and_control/sox1"))
    assert "Data model: Operational Risk and Control \u2014 SOX1" in text
    assert "FROM [SOXRisk] JOIN [SOXControl] ON PARENT([SOXRisk])" in text
    # Vendor is outside the model, so the writer is never shown it.
    assert "Vendor" not in text
    datasources.forget_schema()
