"""
Choosing which tables the model is shown.

A connection can share far more tables than any model's context window holds: the OpenPages demo
shares 164 object types, which describe to roughly 33,000 tokens against a 12,288-token window.
A window that overflows is truncated silently, keeping the tail, so the model ends up insisting
that real object types don't exist. These tests cover choosing instead of overflowing.
"""

from app.datasources import CHARS_PER_TOKEN, DataSource, _fit, _score, _terms, describe


def test_camel_case_names_are_split_into_words():
    assert "process" in _terms("SOXProcess")
    assert "action" in _terms("ActionItem") and "item" in _terms("ActionItem")
    # Runs of capitals are one word, not one word per letter.
    assert "sox" in _terms("SOXRisk")


def test_plurals_match_the_singular_name():
    # People ask about "processes"; the object type is called SOXProcess.
    assert "process" in _terms("How many processes are in scope?")
    assert "risk" in _terms("Show risks by rating")


def test_words_that_fit_every_question_are_ignored():
    # Otherwise "show me a chart of the total" would score against every table equally.
    assert _terms("Show me a chart of the total") == set()


def test_the_table_a_question_names_scores_highest():
    blocks = {
        "openpages.SOXProcess": "[SOXProcess]\n  [OPSS-Proc:Status] enum\n  [OPSS-Proc:Domain] enum",
        "openpages.Vendor": "[Vendor]\n  [OPSS-Vnd:Status] enum",
        "openpages.Workpaper": "[Workpaper]\n  [OPSS-WP:Status] enum",
    }
    wanted = _terms("Show business processes by status and domain")
    scores = {t: _score(t, b, wanted) for t, b in blocks.items()}
    assert scores["openpages.SOXProcess"] > scores["openpages.Vendor"]
    assert scores["openpages.SOXProcess"] > scores["openpages.Workpaper"]


def test_a_field_name_counts_for_less_than_the_table_name():
    name_match = _score("openpages.Vendor", "[Vendor]\n  [Status] enum", _terms("vendor report"))
    field_match = _score("openpages.Workpaper", "[Workpaper]\n  [Vendor] text", _terms("vendor report"))
    assert name_match > field_match


def test_everything_is_shown_when_it_fits():
    blocks = {"a.one": "one\n  x", "a.two": "two\n  y"}
    kept, left_out = _fit(blocks, "anything", budget=10_000)
    assert kept == ["a.one", "a.two"] and left_out == []


def test_what_does_not_fit_is_left_out_rather_than_truncated():
    names = [f"Filler{i}" for i in range(49)] + ["ActionItem"]
    blocks = {f"openpages.{n}": f"[{n}]\n" + ("  [Column] text\n" * 40) for n in names}
    kept, left_out = _fit(blocks, "Show action items by status", budget=2_000)
    assert kept and left_out
    assert len(kept) + len(left_out) == 50
    # The one actually asked about survives the cut, though it was listed last.
    assert "openpages.ActionItem" in kept


def test_the_order_tables_were_chosen_in_is_kept():
    # Relevance decides what is shown; it must not reshuffle what is shown, or the same database
    # reads differently from one question to the next.
    blocks = {f"s.t{i}": f"t{i}\n  col text" for i in range(10)}
    kept, _ = _fit(blocks, "t9 t5", budget=10_000)
    assert kept == sorted(kept, key=lambda t: list(blocks).index(t))


def test_one_table_is_always_shown_even_if_it_alone_is_too_big():
    # Better a single table the model can use than a list of names it cannot.
    blocks = {"s.huge": "huge\n" + ("  col text\n" * 500)}
    kept, left_out = _fit(blocks, "huge", budget=10)
    assert kept == ["s.huge"] and left_out == []


# ---------- the whole description ----------

class FakeClient:
    """One object type per name, each with enough fields to matter against a small budget."""

    def type_fields(self, name):
        return [{"name": f"OPSS-{name}:Field{i}", "type": "text", "values": []} for i in range(30)]


def op_source(types):
    return DataSource(id=99, name="OP", db_type="openpages", version="v1", client=FakeClient(),
                      tables=[f"openpages.{t}" for t in types])


def test_a_huge_schema_is_cut_to_the_budget_and_says_what_was_left_out(monkeypatch):
    from app import datasources
    monkeypatch.setattr(datasources.settings, "ai_schema_budget_tokens", 1200)
    datasources.forget_schema()
    names = ["SOXProcess", "SOXRisk"] + [f"Filler{i}" for i in range(80)]
    text = describe(op_source(names), "Show business processes by status")

    assert "[SOXProcess]" in text                       # what was asked about is described in full
    assert "Also available, but not described above" in text
    assert "Filler70" in text                           # the rest are still named, so it knows they exist
    assert "say so in reply rather than guessing" in text
    # The whole thing has to leave room for a question and an answer.
    assert len(text) < 1200 * CHARS_PER_TOKEN * 2.5
    datasources.forget_schema()


def test_a_small_schema_is_described_in_full_with_no_note(monkeypatch):
    from app import datasources
    monkeypatch.setattr(datasources.settings, "ai_schema_budget_tokens", 6000)
    datasources.forget_schema()
    text = describe(op_source(["SOXProcess", "SOXRisk"]), "anything at all")
    assert "[SOXProcess]" in text and "[SOXRisk]" in text
    assert "Also available" not in text
    datasources.forget_schema()


def test_reading_the_schema_happens_once(monkeypatch):
    from app import datasources
    datasources.forget_schema()
    reads = []

    class Counting(FakeClient):
        def type_fields(self, name):
            reads.append(name)
            return super().type_fields(name)

    source = DataSource(id=98, name="OP", db_type="openpages", version="v1", client=Counting(),
                        tables=["openpages.SOXProcess", "openpages.SOXRisk"])
    datasources.warm_schema(source)
    assert len(reads) == 2
    # Later questions reuse what warming read, however differently they are worded.
    describe(source, "processes by status")
    describe(source, "risks by rating")
    assert len(reads) == 2
    datasources.forget_schema()
