"""
What makes chatting with a database quick: the schema is read once, the model is not asked to
re-read it on every question, and the connection to it is not rebuilt for every call.

None of this changes an answer, which is exactly why it needs its own tests - a cache that quietly
stops caching looks the same from the outside as one that works, only slower.
"""

import time

from app import datasources
from app.ai import providers


# ---------- The schema is read once, then refreshed behind whoever asks next ----------

def _wait_for_refresh(timeout: float = 5.0) -> None:
    """Waits for the background re-read to finish, so the assertion isn't a race."""
    until = time.time() + timeout
    while datasources._refreshing and time.time() < until:
        time.sleep(0.01)


def test_the_schema_is_read_once_and_then_kept(monkeypatch):
    reads = []
    monkeypatch.setattr(datasources, "_read_blocks", lambda src: reads.append(1) or {"t": "t\n  a"})
    datasources.forget_schema()
    source = datasources._builtin(with_engine=True)

    datasources._schema_blocks(source)
    datasources._schema_blocks(source)
    datasources._schema_blocks(source)
    assert len(reads) == 1, "the schema was re-read while a good copy was in hand"


def test_an_expired_schema_is_served_from_the_copy_and_refreshed_behind_it(monkeypatch):
    """The question that arrives after the copy expires is the one that used to pay for it - and
    for OpenPages that is one HTTP request per object type. It must not wait."""
    datasources.forget_schema()
    source = datasources._builtin(with_engine=True)
    key = datasources._cache_key(source)
    datasources._blocks_cache[key] = (0.0, {"old": "the copy in hand"})  # expired long ago

    slow_reads = []

    def slow(src):
        slow_reads.append(1)
        time.sleep(0.2)  # longer than the assertion below allows for
        return {"new": "freshly read"}

    monkeypatch.setattr(datasources, "_read_blocks", slow)

    t0 = time.perf_counter()
    served = datasources._schema_blocks(source)
    waited = time.perf_counter() - t0

    assert served == {"old": "the copy in hand"}, "the stale copy should be served as it is"
    assert waited < 0.1, f"the caller waited {waited:.3f}s for a refresh it should not have waited for"

    _wait_for_refresh()
    assert slow_reads, "the refresh never ran"
    assert datasources._blocks_cache[key][1] == {"new": "freshly read"}


def test_one_refresh_however_many_questions_arrive(monkeypatch):
    """Ten questions in the second a schema expires must not start ten re-reads of it."""
    datasources.forget_schema()
    source = datasources._builtin(with_engine=True)
    key = datasources._cache_key(source)
    datasources._blocks_cache[key] = (0.0, {"old": "x"})

    reads = []

    def slow(src):
        reads.append(1)
        time.sleep(0.15)
        return {"new": "x"}

    monkeypatch.setattr(datasources, "_read_blocks", slow)
    for _ in range(10):
        datasources._schema_blocks(source)
    _wait_for_refresh()
    assert len(reads) == 1, f"{len(reads)} refreshes were started for one expiry"


def test_a_failed_refresh_keeps_the_copy_it_has(monkeypatch):
    """A source that has gone away for a minute must not take the schema with it: the description
    in hand still writes correct SQL, and the next question is answered rather than refused."""
    datasources.forget_schema()
    source = datasources._builtin(with_engine=True)
    key = datasources._cache_key(source)
    datasources._blocks_cache[key] = (0.0, {"old": "still good"})

    def boom(src):
        raise RuntimeError("the database is not answering")

    monkeypatch.setattr(datasources, "_read_blocks", boom)
    assert datasources._schema_blocks(source) == {"old": "still good"}
    _wait_for_refresh()
    assert datasources._blocks_cache[key][1] == {"old": "still good"}
    # The timestamp moved on, so the next question doesn't start the failing read all over again.
    assert datasources._blocks_cache[key][0] > 0.0


def test_a_changed_connection_is_read_again_not_served_stale(monkeypatch):
    """Sharing a new table must show up at once. The version is part of the key, so a change is a
    different key and a blocking read - never a stale copy that leaves the new table invisible."""
    reads = []
    monkeypatch.setattr(datasources, "_read_blocks", lambda src: reads.append(src.version) or {"t": "x"})
    datasources.forget_schema()
    source = datasources._builtin(with_engine=True)

    from dataclasses import replace
    datasources._schema_blocks(source)
    datasources._schema_blocks(replace(source, version="changed"))
    assert len(reads) == 2


# ---------- The schema is not re-read by the model on every question ----------

def test_the_table_descriptions_are_sent_as_a_cached_prefix(monkeypatch):
    """The system prompt is every shared table's fields - the same thousands of tokens on every
    question about that database. Marked as cached, the second question neither pays for them nor
    waits for them. Caching is a prefix match, so nothing per-question may come before it."""
    sent = {}

    class _Response:
        stop_reason = "end_turn"
        content = [type("B", (), {"type": "text", "text": '{"action": "reply", "reply": "hi"}'})()]

    class _Messages:
        @staticmethod
        def create(**kw):
            sent.update(kw)
            return _Response()

    class _Client:
        messages = _Messages()

    monkeypatch.setattr(providers, "_claude_client", lambda key: _Client())
    providers._claude(providers.ModelSpec(provider="anthropic", model="claude-haiku-4-5", api_key="k"),
                      "SCHEMA AND RULES", "Question: how many orders?", {"type": "object"})

    assert sent["system"] == [{"type": "text", "text": "SCHEMA AND RULES",
                               "cache_control": {"type": "ephemeral"}}]
    # The question belongs in the message, behind the cached prefix - in front of it, every
    # question would be a different prefix and nothing would ever be reused.
    assert sent["messages"] == [{"role": "user", "content": "Question: how many orders?"}]


# ---------- The connection to the model is not rebuilt for every call ----------

def test_the_same_key_gets_the_same_client():
    """A chat message is two calls and a dashboard is dozens; a client per call means a fresh TLS
    handshake before each of them."""
    providers.forget_clients()
    first = providers._claude_client("key-one")
    assert providers._claude_client("key-one") is first
    assert providers._claude_client("key-two") is not first


def test_a_replaced_key_is_not_still_used():
    """The kept client holds the key it was built with, so changing one has to drop them."""
    providers.forget_clients()
    before = providers._claude_client("old-key")
    providers.forget_clients()
    assert providers._claude_client("old-key") is not before
