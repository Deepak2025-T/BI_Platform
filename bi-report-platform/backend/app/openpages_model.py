"""
Data models: the IBM OpenPages object models, read as entities and the relationships between them.

OpenPages ships a reporting framework whose namespaces each describe one object model - which
object types a solution uses and how they nest. Openpages_model/Model_name_space.txt holds one
namespace per pair of lines: the namespace path, then its edges as "Parent|Child" separated by
commas. A bare name with no "|" is an object type the namespace uses but hangs nowhere in
particular.

Those edges are the whole model. OpenPages has no foreign keys: an object is related to another by
*being underneath it* in the hierarchy, which is why its SQL joins with PARENT, CHILD, ANCESTOR and
DESCENDANT rather than column equality (see connections/openpages.py). So an edge here means "a
Child sits under a Parent", and that is exactly the join the query writer needs.

A self-edge (SOXBusEntity|SOXBusEntity) is a type that nests under itself - business entities form
a tree - and is kept, flagged, and drawn as a loop rather than a line to nowhere.

The models are shipped, not discovered: they come from the framework, so they are the same on every
installation. What differs per installation is which types actually exist and what fields they
carry, and that is read live from the connection (see fields_for) and can be refreshed.
"""

import re
import time
from dataclasses import dataclass, field
from pathlib import Path

# The shipped copy, with the working copy in the repo as a fallback so an edited file is picked up.
_PACKAGED = Path(__file__).with_name("data") / "openpages_namespaces.txt"
_IN_REPO = Path(__file__).resolve().parents[2] / "Openpages_model" / "Model_name_space.txt"

_PATH_LINE = re.compile(r"/Models/(?P<solution>[^/]+)/Namespaces/(?P<namespace>[^/]+)/Object Model\s*$")

FIELD_CACHE_SECONDS = 900


@dataclass(frozen=True)
class Relationship:
    """A parent type and the child type that sits under it."""
    parent: str
    child: str

    @property
    def is_self(self) -> bool:
        return self.parent == self.child


@dataclass
class DataModel:
    key: str            # "operational_risk_and_control/orm1", stable and URL-safe
    solution: str       # "Operational Risk and Control"
    namespace: str      # "ORM1"
    entities: list[str] = field(default_factory=list)
    relationships: list[Relationship] = field(default_factory=list)

    @property
    def name(self) -> str:
        return f"{self.solution} — {self.namespace}"

    @property
    def is_default(self) -> bool:
        return self.namespace.upper() == "DEFAULT"


def _title(raw: str) -> str:
    return raw.replace("_", " ").strip()


def _parse(text: str) -> list[DataModel]:
    models: list[DataModel] = []
    pending: DataModel | None = None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        found = _PATH_LINE.search(line)
        if found:
            # A path line starts a new model. The edges are on the next non-blank line.
            namespace = found.group("namespace").strip()
            pending = DataModel(key=f"{found.group('solution').lower()}/{namespace.lower()}",
                                solution=_title(found.group("solution")), namespace=namespace)
            models.append(pending)
            continue
        if pending is None:
            continue
        for part in line.split(","):
            part = part.strip()
            if not part:
                continue
            parent, sep, child = part.partition("|")
            parent, child = parent.strip(), child.strip()
            if sep and parent and child:
                rel = Relationship(parent, child)
                if rel not in pending.relationships:
                    pending.relationships.append(rel)
                names = (parent, child)
            else:
                names = (parent,)
            for n in names:
                if n and n not in pending.entities:
                    pending.entities.append(n)
        pending = None  # one edge line per model; anything after it starts a fresh one
    return [m for m in models if m.entities]


def _load() -> list[DataModel]:
    for path in (_PACKAGED, _IN_REPO):
        try:
            return _parse(path.read_text(encoding="utf-8-sig"))
        except OSError:
            continue
    return []


MODELS: list[DataModel] = _load()
_BY_KEY: dict[str, DataModel] = {m.key: m for m in MODELS}


def get(key: str | None) -> DataModel | None:
    return _BY_KEY.get((key or "").strip().lower())


def parents_of(model: DataModel, child: str) -> list[str]:
    return [r.parent for r in model.relationships if r.child == child and not r.is_self]


def children_of(model: DataModel, parent: str) -> list[str]:
    return [r.child for r in model.relationships if r.parent == parent and not r.is_self]


def roots(model: DataModel) -> list[str]:
    """Entities nothing else sits above - where the hierarchy starts."""
    return [e for e in model.entities if not parents_of(model, e)]


def depth_of(model: DataModel) -> dict[str, int]:
    """How far below a root each entity sits, for laying the diagram out in rows. A model that
    loops back on itself stops at the depth first reached rather than walking round forever."""
    levels: dict[str, int] = {e: 0 for e in roots(model)}
    frontier = list(levels)
    ceiling = len(model.entities)
    while frontier:
        nxt = []
        for parent in frontier:
            for child in children_of(model, parent):
                want = levels[parent] + 1
                if want <= levels.get(child, -1) or want > ceiling:
                    continue
                levels[child] = want
                nxt.append(child)
        frontier = nxt
    for e in model.entities:
        levels.setdefault(e, 0)
    return levels


def join_hints(model: DataModel, limit: int = 40) -> str:
    """The relationships written as the joins OpenPages SQL actually takes."""
    lines = []
    for r in model.relationships[:limit]:
        if r.is_self:
            lines.append(f"- [{r.parent}] nests under itself: "
                         f"FROM [{r.parent}] JOIN [{r.parent}] ON PARENT([{r.parent}])")
        else:
            lines.append(f"- [{r.child}] sits under [{r.parent}]: "
                         f"FROM [{r.parent}] JOIN [{r.child}] ON PARENT([{r.parent}])")
    return "\n".join(lines)


def model_note(model: DataModel) -> str:
    """What the query writer is told about the chosen model."""
    return (f"\nData model: {model.name}. Use only the object types above, and join them the way "
            f"this model relates them (ANCESTOR instead of PARENT to reach any level below):\n"
            f"{join_hints(model)}\n")


# ---------- the live half: which types exist here, and what fields they carry ----------

_fields_cache: dict[tuple, tuple[float, list[dict]]] = {}


def forget(connection_id: int | None = None):
    """Drops cached field lists, so the next read goes back to OpenPages."""
    if connection_id is None:
        _fields_cache.clear()
        return
    for key in [k for k in _fields_cache if k[0] == connection_id]:
        del _fields_cache[key]


def fields_for(source, entity: str) -> list[dict]:
    """One entity's fields, from the connection, cached. [] when the type isn't in this
    installation or can't be read - the diagram then shows the box as missing."""
    key = (source.id, source.version, entity)
    hit = _fields_cache.get(key)
    if hit and time.time() - hit[0] < FIELD_CACHE_SECONDS:
        return hit[1]
    try:
        fields = source.client.type_fields(entity)
    except Exception:
        fields = []
    _fields_cache[key] = (time.time(), fields)
    return fields
