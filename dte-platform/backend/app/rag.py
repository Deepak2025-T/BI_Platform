"""pgvector-backed retrieval of schema context, glossary terms and verified prompt→SQL examples."""
from __future__ import annotations

from sqlalchemy import delete, select

from .connectors import introspect
from .db import DbConnection, RagChunk, SessionLocal, utcnow
from .llm.embeddings import embed


def table_doc(t: dict) -> str:
    lines = [f"TABLE {t['table']}" + (f" -- {t['comment']}" if t.get("comment") else "")]
    for c in t["columns"]:
        extra = []
        if c["name"] in t.get("primary_key", []):
            extra.append("PK")
        if c.get("comment"):
            extra.append(c["comment"])
        if c.get("samples"):
            extra.append("e.g. " + ", ".join(c["samples"]))
        lines.append(f"  {c['name']} {c['type']}" + (f"  -- {'; '.join(extra)}" if extra else ""))
    for fk in t.get("foreign_keys", []):
        lines.append(f"  FK ({', '.join(fk['columns'])}) -> {fk['ref_table']}({', '.join(fk['ref_columns'])})")
    return "\n".join(lines)


def index_connection(conn: DbConnection, glossary: dict[str, str] | None = None) -> int:
    tables = introspect(conn)
    docs = [(t["table"], table_doc(t), {"columns": [c["name"] for c in t["columns"]],
                                        "fks": t["foreign_keys"]}) for t in tables]
    vecs = embed([d[1] for d in docs]) if docs else []
    with SessionLocal() as db:
        db.execute(delete(RagChunk).where(RagChunk.connection_id == conn.id, RagChunk.kind == "table"))
        for (ref, content, meta), v in zip(docs, vecs):
            db.add(RagChunk(connection_id=conn.id, kind="table", ref=ref, content=content, meta=meta, embedding=v))
        for term, definition in (glossary or {}).items():
            add_glossary(conn.id, term, definition, db=db)
        c = db.get(DbConnection, conn.id)
        c.indexed_at = utcnow()
        db.commit()
    return len(docs)


def add_glossary(conn_id: int, term: str, definition: str, db=None) -> None:
    own = db is None
    db = db or SessionLocal()
    content = f"BUSINESS TERM {term}: {definition}"
    db.add(RagChunk(connection_id=conn_id, kind="glossary", ref=term, content=content, meta={}, embedding=embed([content])[0]))
    if own:
        db.commit()
        db.close()


def add_example(conn_id: int, prompt: str, sql: str) -> None:
    """Store a verified (published) prompt→SQL pair; retrieved as few-shot examples later (learning loop)."""
    content = f"QUESTION: {prompt}\nSQL: {sql}"
    with SessionLocal() as db:
        db.add(RagChunk(connection_id=conn_id, kind="example", ref=prompt[:255], content=content,
                        meta={"sql": sql}, embedding=embed([prompt])[0]))
        db.commit()


def retrieve(conn_id: int, question: str, k_tables: int = 6, k_examples: int = 3) -> dict:
    qv = embed([question])[0]
    with SessionLocal() as db:
        def top(kind, k):
            stmt = (select(RagChunk).where(RagChunk.connection_id == conn_id, RagChunk.kind == kind)
                    .order_by(RagChunk.embedding.cosine_distance(qv)).limit(k))
            return list(db.scalars(stmt))
        tables = top("table", k_tables)
        # expand with FK neighbours so joins are possible even if a bridge table ranked low
        names = {t.ref for t in tables}
        neighbours = {fk["ref_table"] for t in tables for fk in (t.meta or {}).get("fks", [])} - names
        if neighbours:
            tables += list(db.scalars(select(RagChunk).where(
                RagChunk.connection_id == conn_id, RagChunk.kind == "table", RagChunk.ref.in_(neighbours))))
        glossary = top("glossary", 4)
        examples = top("example", k_examples)
    return {
        "tables": [t.ref for t in tables],
        "schema_text": "\n\n".join(t.content for t in tables),
        "glossary_text": "\n".join(g.content for g in glossary),
        "examples_text": "\n\n".join(e.content for e in examples),
    }
