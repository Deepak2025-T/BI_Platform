"""
IBM OpenPages through its REST API, instead of a database driver.

Queries go to the Query Service (GET {base}/query?q=...), which takes OpenPages SQL: object types
and fields in [brackets], joins with PARENT/CHILD/ANCESTOR/DESCENDANT, no LIMIT. It runs with the
signed-in account's OpenPages permissions, so use an account that can only read.

"Tables" are object types (SOXRisk, SOXIssue, Finding...). A manager picks which ones people may
query on the Connections page, the same as tables for a database.

Sign-in, set per connection:
- basic: username and password
- oauth2: client credentials (OpenPages 9.1+): client id and secret, exchanged at the token URL
- mpjwt: a MicroProfile JWT, pasted as the secret and sent as a Bearer token
- iam: an IBM Cloud API key, exchanged for an access token at IBM Cloud IAM
- mtls: a client certificate and private key (PEM), optionally with a username and password too
"""

import os
import re
import ssl
import tempfile
import threading
import time
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import httpx

SCHEMA = "openpages"  # object types are listed, and allowed, as "openpages.<type>"
AUTH_TYPES = {
    "basic": "Basic Auth (username and password)",
    "oauth2": "OAuth 2.0 client credentials (9.1+)",
    "mpjwt": "MP-JWT (MicroProfile token)",
    "iam": "IBM Cloud IAM token",
    "mtls": "Client certificate (mutual TLS)",
}
IAM_TOKEN_URL = "https://iam.cloud.ibm.com/identity/token"
TIMEOUT = 30  # seconds per request
MAX_TOKEN_REDIRECTS = 3  # same-host hops a token request will follow before giving up
MAX_PAGES = 20

# Fields every object type has.
SYSTEM_FIELDS = ["Resource ID", "Name", "Description", "Location", "Created By", "Creation Date",
                 "Last Modification Date", "Last Modified By"]

# How to write OpenPages SQL, for the AI model. Field names differ between installations, so the
# model gets each type's real fields too (see type_fields).
SQL_GUIDE = """OpenPages Query Service SQL (not database SQL). It is much smaller than normal SQL:
- Wrap EVERY object type and field in square brackets and always write [Type].[Field]:
  SELECT [SOXIssue].[Name], [SOXIssue].[OPSS-Iss:Status] FROM [SOXIssue]
- System fields on every type: [Resource ID], [Name], [Description], [Location], [Created By],
  [Creation Date], [Last Modification Date], [Last Modified By].
- WHERE supports =, <>, <, >, >=, <=, LIKE '%text%', IN ('a', 'b'), IS NULL, IS NOT NULL, AND, OR.
  Text in single quotes: 'Open'. Dates: '2024-01-01'. ORDER BY ... DESC works.
- The only function is COUNT, and only on ONE object type (no JOIN in that query):
    SELECT [SOXIssue].[OPSS-Iss:Status], COUNT([SOXIssue].[Resource ID]) FROM [SOXIssue]
    GROUP BY [SOXIssue].[OPSS-Iss:Status] ORDER BY COUNT([SOXIssue].[Resource ID]) DESC
  The count column comes back named "Count_Resource ID"; use that name in the chart's y.
  A single total: SELECT COUNT([Finding].[Resource ID]) FROM [Finding] WHERE [Finding].[OPSS-Finding:Status] = 'Open'
- Joins follow the object hierarchy, never column equality, and list rows (no COUNT):
    children of a parent: FROM [AuditProgram] JOIN [Finding] ON PARENT([AuditProgram])
    parent of a child:    FROM [Finding] JOIN [AuditProgram] ON CHILD([Finding])
    any level below:      FROM [SOXRisk] JOIN [SOXIssue] ON ANCESTOR([SOXRisk]) WHERE [SOXRisk].[Resource ID] = <id>
  Use one JOIN; chains of several joins often fail.
- Columns keep their field names: never use AS. When two types share a field name (both [Name]),
  the columns come back as "AuditProgram Name" and "Finding Name".
- Not supported: AS, DISTINCT, SUM, AVG, MIN, MAX, date or text functions (no YEAR, MONTH), CASE,
  LIMIT, TOP, subqueries, UNION, WITH, and any change to data. Rows are capped automatically.
- Enum fields often have empty values; add WHERE [T].[Field] IS NOT NULL to leave them out."""


class OpenPagesError(Exception):
    """OpenPages refused or failed the request. The message is safe to show."""


class UnsafeOpenPagesSQL(Exception):
    """The OpenPages SQL can't run. The message explains why."""


@dataclass
class OPSpec:
    base_url: str  # https://host/grc/api
    auth_type: str = "basic"
    username: str = ""
    secret: str = ""  # password, client secret, JWT or IAM API key, depending on auth_type
    client_id: str = ""
    token_url: str = ""
    scope: str = ""  # OAuth 2.0: only when the provider insists on one
    client_cert: str = ""  # PEM
    client_key: str = ""  # PEM
    verify: bool = True


def normalize_base(url: str) -> str:
    """Accepts the host, the /grc/api URL or a full /grc/api/query URL; returns https://host/grc/api."""
    value = (url or "").strip().rstrip("/")
    parsed = urlparse(value)
    if parsed.scheme not in ("https", "http") or not parsed.netloc:
        raise ValueError("Enter the OpenPages URL starting with https://, e.g. https://openpages.company.com/grc/api")
    if parsed.scheme == "http" and parsed.hostname not in ("localhost", "127.0.0.1"):
        raise ValueError("Use https:// for OpenPages servers (http only works for localhost).")
    if parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise ValueError("Enter only the API URL, without query parameters or credentials.")
    path = parsed.path.rstrip("/")
    for marker in ("/opgrc/api", "/grc/api"):
        index = path.lower().find(marker)
        if index >= 0:
            path = path[:index]
            break
    else:
        if path:
            raise ValueError("Enter the server address or its /grc/api URL.")
    return f"{parsed.scheme}://{parsed.netloc}{path}/grc/api"


# ---------- Signing in and calling the API ----------

class OpenPagesClient:
    """One per saved connection (see get_client). Keeps the access token until it expires."""

    def __init__(self, spec: OPSpec):
        self.spec = spec
        self.base = normalize_base(spec.base_url)
        self._token: tuple[str, float] | None = None
        self._lock = threading.Lock()
        self._verify = self._ssl_context()

    def _ssl_context(self):
        if self.spec.auth_type != "mtls":
            return self.spec.verify
        if not self.spec.client_cert.strip() or not self.spec.client_key.strip():
            raise OpenPagesError("Paste the client certificate and its private key (PEM) for mutual TLS.")
        ctx = ssl.create_default_context()
        if not self.spec.verify:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        # ssl reads the certificate from files; they exist only while it's loaded.
        paths = []
        try:
            for pem in (self.spec.client_cert, self.spec.client_key):
                fd, path = tempfile.mkstemp(suffix=".pem")
                paths.append(path)
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(pem.strip() + "\n")
            ctx.load_cert_chain(paths[0], paths[1])
        except ssl.SSLError as err:
            raise OpenPagesError(f"The client certificate or key couldn't be read: {err.reason or err}")
        finally:
            for path in paths:
                try:
                    os.remove(path)
                except OSError:
                    pass
        return ctx

    def _headers(self) -> dict:
        headers = {"Accept": "application/json"}
        kind = self.spec.auth_type
        if kind == "basic" or (kind == "mtls" and self.spec.username):
            if not self.spec.username or not self.spec.secret:
                raise OpenPagesError("Enter the OpenPages username and password.")
            return headers  # sent with httpx's basic auth
        if kind == "mpjwt":
            token = self.spec.secret.strip().removeprefix("Bearer ").strip()
            if not token:
                raise OpenPagesError("Paste the MP-JWT token.")
            headers["Authorization"] = f"Bearer {token}"
        elif kind in ("oauth2", "iam"):
            headers["Authorization"] = f"Bearer {self._access_token()}"
        return headers

    def _auth(self):
        if self.spec.auth_type == "basic" or (self.spec.auth_type == "mtls" and self.spec.username):
            return httpx.BasicAuth(self.spec.username, self.spec.secret)
        return None

    def _access_token(self) -> str:
        with self._lock:
            if self._token and self._token[1] > time.time() + 30:
                return self._token[0]
            if self.spec.auth_type == "iam":
                if not self.spec.secret:
                    raise OpenPagesError("Enter the IBM Cloud API key.")
                url = self.spec.token_url.strip() or IAM_TOKEN_URL
                data = {"grant_type": "urn:ibm:params:oauth:grant-type:apikey", "apikey": self.spec.secret}
                attempts = [(data, None)]
            else:
                if not self.spec.token_url.strip() or not self.spec.client_id or not self.spec.secret:
                    raise OpenPagesError("Enter the token URL, client ID and client secret.")
                url = self.spec.token_url.strip()
                data = {"grant_type": "client_credentials"}
                if self.spec.scope.strip():
                    data["scope"] = self.spec.scope.strip()
                # Two ways to present the client, in the order OAuth 2.0 prefers them. WebSphere
                # Liberty, which serves OpenPages' /oauth2/endpoint/<provider>/token, is configured
                # for client_secret_basic by default and answers a body-only request without an
                # access_token; other servers only accept the credentials in the body.
                attempts = [({**data}, httpx.BasicAuth(self.spec.client_id, self.spec.secret)),
                            ({**data, "client_id": self.spec.client_id,
                              "client_secret": self.spec.secret}, None)]
            if not _secure_enough(url):
                raise OpenPagesError("The token URL must start with https://.")
            problem = ""
            for form, auth in attempts:
                r, redirect_problem = self._post_token(url, form, auth)
                if r is None:
                    # A redirect has nothing to do with how the client was presented, so trying the
                    # other way would only repeat it: say what happened and stop.
                    raise OpenPagesError(f"The token URL didn't answer with a token. {redirect_problem}")
                token, expires, problem = _read_token(r)
                if token:
                    self._token = (token, time.time() + expires)
                    return token
            how = "as a Basic header and in the body" if len(attempts) > 1 else ""
            raise OpenPagesError(f"The token server didn't return an access token{' (tried the client ' + how + ')' if how else ''}. {problem}".strip())

    def _post_token(self, url: str, form: dict, auth) -> tuple[httpx.Response | None, str]:
        """POSTs the token request, following redirects by hand. httpx doesn't follow them, and
        letting a client follow a 302 would turn the POST into a GET and drop the form, so each hop
        is re-sent as a POST. A redirect off this host is never followed: it would hand the client
        secret to whatever answered, which for an SSO login page is exactly the wrong thing."""
        seen = []
        for _ in range(MAX_TOKEN_REDIRECTS + 1):
            try:
                r = httpx.post(url, data=form, auth=auth, timeout=TIMEOUT, verify=self._verify,
                               headers={"Accept": "application/json",
                                        "Content-Type": "application/x-www-form-urlencoded"})
            except httpx.HTTPError as err:
                raise OpenPagesError(f"Couldn't reach the token server: {_short(err)}")
            if r.status_code not in (301, 302, 303, 307, 308):
                return r, ""
            target = r.headers.get("location", "").strip()
            if not target:
                return None, (f"It answered HTTP {r.status_code} (a redirect) with no Location header, so there "
                              "is nowhere to follow. Check the token URL with your OpenPages administrator.")
            target = urljoin(url, target)
            if urlparse(target).netloc != urlparse(url).netloc or not _secure_enough(target):
                return None, (f"It answered HTTP {r.status_code} and redirected to {_clip(target, 120)}, on another "
                              "server. The client secret was not sent there. A token endpoint should answer "
                              "directly; this one looks like it sits behind a sign-in page or gateway.")
            seen.append(target)
            url = target
        return None, (f"It kept redirecting ({' -> '.join(_clip(u, 80) for u in seen)}). "
                      "Check the token URL with your OpenPages administrator.")

    def get(self, path_or_url: str, params: dict | None = None):
        url = path_or_url if path_or_url.startswith("http") else f"{self.base}/{path_or_url.lstrip('/')}"
        if urlparse(url).netloc != urlparse(self.base).netloc:
            raise OpenPagesError("OpenPages pointed to a different server; the request was not sent.")
        try:
            r = httpx.get(url, params=params, headers=self._headers(), auth=self._auth(), timeout=TIMEOUT,
                          verify=self._verify)
        except httpx.HTTPError as err:
            raise OpenPagesError(f"Couldn't reach OpenPages: {_short(err)}")
        if r.status_code == 401 and self.spec.auth_type in ("oauth2", "iam"):
            self._token = None  # expired early: sign in again once
            r = httpx.get(url, params=params, headers=self._headers(), auth=self._auth(), timeout=TIMEOUT,
                          verify=self._verify)
        if r.status_code in (401, 403):
            # A 401 on basic auth is nearly always the username: OpenPages wants the login name
            # held in its own user record, which is often not the person's email address.
            hint = (" Check the username is the OpenPages login name (often not the email address) "
                    "and the password is current." if self.spec.auth_type == "basic" and r.status_code == 401 else "")
            raise OpenPagesError(f"OpenPages refused the sign-in or the account can't do this "
                                 f"(HTTP {r.status_code}).{hint}")
        if r.status_code >= 400:
            raise OpenPagesError(f"OpenPages returned HTTP {r.status_code}: {_error_text(r)}")
        try:
            return r.json()
        except ValueError:
            raise OpenPagesError("OpenPages didn't answer with JSON. Check the URL ends in /grc/api, and that sign-in "
                                 "isn't redirected to a single sign-on page.")

    # ---------- Object types and fields ----------

    def list_types(self) -> list[str]:
        payload = self.get("types")
        items = payload if isinstance(payload, list) else _first_list(payload)
        names = sorted({str(t.get("name")) for t in items if isinstance(t, dict) and t.get("name")}, key=str.lower)
        if not names:
            raise OpenPagesError("OpenPages returned no object types for this account.")
        return names

    def type_fields(self, type_name: str) -> list[dict]:
        """[{"name", "type", "values"}] for one object type; the system fields when the definition
        can't be read."""
        fields: list[dict] = []
        try:
            payload = self.get(f"types/{type_name}")
            for f in _find_field_definitions(payload):
                fields.append({"name": str(f["name"]), "type": str(f.get("dataType", "")).replace("_TYPE", "").lower(),
                               "values": _enum_names(f)})
        except OpenPagesError:
            pass
        have = {f["name"].lower() for f in fields}
        system = [{"name": n, "type": "date" if "Date" in n else "text", "values": []}
                  for n in SYSTEM_FIELDS if n.lower() not in have]
        return system + fields

    # ---------- Queries ----------

    def query(self, sql: str, max_rows: int) -> tuple[list[str], list[list], bool]:
        """Runs one checked query. Returns (columns, rows, truncated)."""
        want = max_rows + 1
        params = {"q": sql, "pageSize": min(want, 500), "maxRows": want, "caseInsensitive": "true"}
        payload = self.get("query", params)
        labels = select_labels(sql)
        records = _rows(payload, labels)
        pages = 1
        while len(records) < want and pages < MAX_PAGES:
            nxt = _next_link(payload)
            if not nxt:
                break
            payload = self.get(urljoin(self.base + "/", nxt))
            records += _rows(payload, labels)
            pages += 1
        truncated = len(records) > max_rows
        records = records[:max_rows]
        columns: list[str] = []
        for rec in records:
            for k in rec:
                if k not in columns:
                    columns.append(k)
        rows = [[rec.get(c) for c in columns] for rec in records]
        _numbers(rows)
        return columns, rows, truncated


# One client per saved connection, rebuilt when the connection changes.
_clients: dict[int, tuple[str, OpenPagesClient]] = {}


def get_client(connection_id: int, version: str, spec: OPSpec) -> OpenPagesClient:
    cached = _clients.get(connection_id)
    if cached and cached[0] == version:
        return cached[1]
    client = OpenPagesClient(spec)
    _clients[connection_id] = (version, client)
    return client


def forget_client(connection_id: int):
    _clients.pop(connection_id, None)


def run_test(client: OpenPagesClient) -> dict:
    """Signs in and lists the object types, like a database test lists tables."""
    t0 = time.perf_counter()
    types = client.list_types()
    return {"elapsed_ms": round((time.perf_counter() - t0) * 1000), "server_version": "",
            "schemas": [{"schema": SCHEMA, "tables": [{"name": t, "kind": "table"} for t in types]}],
            "table_count": len(types)}


# ---------- Checking AI-written OpenPages SQL ----------

_WRITE_WORDS = re.compile(r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|EXEC|EXECUTE|MERGE|CALL|GRANT|"
                          r"REVOKE|INTO|UNION|INTERSECT|EXCEPT|WITH)\b", re.I)
_TYPE_REF = re.compile(r"\b(FROM|JOIN)\s+(\[(?:[^\]]|\]\])+\]|\S+)", re.I)
_FUNCTION = re.compile(r"\b([A-Za-z_]+)\s*\(")
_HIERARCHY = {"PARENT", "CHILD", "ANCESTOR", "DESCENDANT"}
_KEYWORDS = {"SELECT", "FROM", "WHERE", "AND", "OR", "NOT", "IN", "ON", "BY", "HAVING", "IS", "LIKE", "JOIN"}


def mask(sql: str, brackets: bool = True) -> str:
    """The SQL with quoted text (and bracketed names) blanked out, keeping every position."""
    pattern = r"'(?:''|[^'])*'|\[(?:[^\]]|\]\])*\]" if brackets else r"'(?:''|[^'])*'"
    return re.sub(pattern, lambda m: " " * len(m.group()), sql)


def query_types(sql: str) -> list[str]:
    """The object types a query reads (after FROM and JOIN), in order."""
    out = []
    masked = mask(sql, brackets=False)
    for m in _TYPE_REF.finditer(masked):
        ref = sql[m.start(2):m.end(2)]
        if ref.startswith("["):
            name = ref[1:-1].replace("]]", "]")
            if name not in out:
                out.append(name)
    return out


def check_sql(sql: str, allowed: set[str]) -> str:
    """Returns the query to run, or raises UnsafeOpenPagesSQL. allowed: lower-case "openpages.<type>"."""
    text = re.sub(r"^\s*```(?:sql)?\s*|\s*```\s*$", "", (sql or "").strip(), flags=re.I).strip().rstrip(";").strip()
    if not text:
        raise UnsafeOpenPagesSQL("No SQL was written.")
    masked = mask(text)
    if text.count("'") % 2 or masked.count("[") or masked.count("]"):
        raise UnsafeOpenPagesSQL("The SQL has an unclosed quote or bracket.")
    if not re.match(r"^\s*SELECT\b", masked, re.I):
        raise UnsafeOpenPagesSQL("Only SELECT queries can run.")
    if re.search(r"--|/\*|\*/", masked):
        raise UnsafeOpenPagesSQL("SQL comments aren't allowed.")
    if ";" in masked:
        raise UnsafeOpenPagesSQL("Only one statement can run at a time.")
    if m := _WRITE_WORDS.search(masked):
        raise UnsafeOpenPagesSQL(f"{m.group(1).upper()} isn't allowed. Only one plain SELECT can run.")
    if re.search(r"\(\s*SELECT\b", masked, re.I):
        raise UnsafeOpenPagesSQL("Subqueries aren't supported by OpenPages SQL.")
    if re.search(r"\b(LIMIT|TOP|OFFSET|FETCH)\b", masked, re.I):
        raise UnsafeOpenPagesSQL("OpenPages SQL has no LIMIT or TOP; rows are capped automatically. Remove it.")
    if re.search(r"\bAS\b", masked, re.I):
        raise UnsafeOpenPagesSQL("OpenPages SQL doesn't support AS. Remove the aliases; columns keep their field names.")
    if re.search(r"\bDISTINCT\b", masked, re.I):
        raise UnsafeOpenPagesSQL("OpenPages SQL doesn't support DISTINCT. Use GROUP BY with COUNT instead.")
    functions = {f.upper() for f in _FUNCTION.findall(masked)} - _HIERARCHY - _KEYWORDS
    if functions - {"COUNT"}:
        raise UnsafeOpenPagesSQL(f"OpenPages SQL has no {', '.join(sorted(functions - {'COUNT'}))} function. "
                                 "The only function is COUNT.")
    if "COUNT" in functions and re.search(r"\bJOIN\b", masked, re.I):
        raise UnsafeOpenPagesSQL("OpenPages can only COUNT one object type: remove the JOIN, or list rows without COUNT.")
    bare = {t.split(".", 1)[-1] for t in allowed}
    unmasked_refs = mask(text, brackets=False)
    for m in _TYPE_REF.finditer(unmasked_refs):
        ref = text[m.start(2):m.end(2)]
        if not ref.startswith("["):
            raise UnsafeOpenPagesSQL(f"Write object types in brackets, e.g. FROM [SOXIssue] (found {ref}).")
        name = ref[1:-1].replace("]]", "]")
        if name.lower() not in bare:
            raise UnsafeOpenPagesSQL(f"The object type [{name}] isn't one of the types you can query.")
    if not query_types(text):
        raise UnsafeOpenPagesSQL("The query needs FROM [ObjectType].")
    return text


def select_labels(sql: str) -> list[str]:
    """For each item in the SELECT list, a column name for joined fields that share a name:
    "[AuditProgram].[Name], [Finding].[Name]" -> ["AuditProgram Name", "Finding Name"]. Other items
    get "" (they keep the name OpenPages gives them)."""
    masked = mask(sql)
    start = re.match(r"\s*SELECT\b", masked, re.I)  # not \s+: a masked [name] is spaces too
    end = re.search(r"\bFROM\b", masked, re.I)
    if not start or not end:
        return []
    items, depth, begin = [], 0, start.end()
    for i in range(start.end(), end.start()):
        ch = masked[i]
        depth += ch == "("
        depth -= ch == ")"
        if ch == "," and depth == 0:
            items.append(sql[begin:i])
            begin = i + 1
    items.append(sql[begin:end.start()])
    parsed = []
    for item in items:
        m = re.fullmatch(r"\s*\[((?:[^\]]|\]\])+)\]\s*\.\s*\[((?:[^\]]|\]\])+)\]\s*", item)
        parsed.append((m.group(1).replace("]]", "]"), m.group(2).replace("]]", "]")) if m else None)
    fields = [p[1].lower() for p in parsed if p]
    return [f"{p[0]} {p[1]}" if p and fields.count(p[1].lower()) > 1 else "" for p in parsed]


# ---------- Dashboard filters ----------

def quote(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def field_ref(type_name: str, field: str) -> str:
    return f"[{type_name.replace(']', ']]')}].[{field.replace(']', ']]')}]"


def add_conditions(sql: str, conditions: list[str]) -> str:
    """Adds conditions to the query's WHERE (or a new WHERE), before GROUP BY / ORDER BY / HAVING."""
    if not conditions:
        return sql
    cond = " AND ".join(f"({c})" for c in conditions)
    masked = mask(sql)
    tail = re.search(r"\b(GROUP\s+BY|ORDER\s+BY|HAVING)\b", masked, re.I)
    cut = tail.start() if tail else len(sql)
    head, rest = sql[:cut], sql[cut:]
    where = re.search(r"\bWHERE\b", masked[:cut], re.I)
    if where:
        head = f"{head[:where.end()]} {cond} AND ({head[where.end():].strip()})"
    else:
        head = f"{head.rstrip()} WHERE {cond}"
    return f"{head} {rest}".strip()


# ---------- Reading responses ----------

def _rows(payload, labels: list[str] | None = None) -> list[dict]:
    """Rows as {column name: value}, from the shapes the Query Service returns. Fields come in SELECT
    order; labels (from select_labels) rename joined fields that share a name."""
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        rows = payload.get("rows")
        if rows is None:
            rows = payload.get("results", payload.get("items", []))
        if isinstance(rows, dict):
            rows = rows.get("row", rows.get("items", []))
    else:
        raise OpenPagesError("OpenPages answered in an unexpected format.")
    if not isinstance(rows, list):
        raise OpenPagesError("OpenPages answered in an unexpected format.")
    out = []
    for row in rows:
        if not isinstance(row, dict):
            out.append({"value": row})
            continue
        fields = row.get("fields")
        if isinstance(fields, dict):
            fields = fields.get("field", [])
        if not isinstance(fields, list):
            out.append({k: v for k, v in row.items() if not isinstance(v, (dict, list))})
            continue
        rec = {}
        positional = labels and len(labels) == len(fields)
        for i, f in enumerate(fields):
            if not isinstance(f, dict):
                continue
            name = str(f.get("name", f.get("fieldName", "value")))
            if positional and labels[i]:
                name = labels[i]
            while name in rec:
                name += " (2)"
            value = f.get("value", f.get("enumValue", f.get("values", f.get("currencyValue"))))
            if isinstance(value, dict):
                value = value.get("name", value.get("localizedLabel", value.get("baseAmount", value.get("amount"))))
            elif isinstance(value, list):
                value = ", ".join(str(v.get("name", v)) if isinstance(v, dict) else str(v) for v in value)
            rec[name] = value
        out.append(rec)
    return out


def _next_link(payload) -> str | None:
    links = payload.get("links") if isinstance(payload, dict) else None
    if isinstance(links, dict):
        links = links.get("link", [])
    for link in links or []:
        if isinstance(link, dict) and str(link.get("rel", "")).lower() == "next" and link.get("href"):
            return str(link["href"])
    return None


_NUMBER = re.compile(r"^-?\d+(\.\d+)?$")


def _numbers(rows: list[list]):
    """Columns whose values are all numbers written as text become numbers, so they can be charted."""
    if not rows:
        return
    for i in range(len(rows[0])):
        values = [r[i] for r in rows if r[i] not in (None, "")]
        if values and all(isinstance(v, str) and _NUMBER.match(v.strip()) for v in values):
            for r in rows:
                if isinstance(r[i], str) and r[i].strip():
                    v = r[i].strip()
                    r[i] = float(v) if "." in v else int(v)


def _first_list(payload) -> list:
    if isinstance(payload, dict):
        for v in payload.values():
            if isinstance(v, list):
                return v
            if isinstance(v, dict):
                inner = _first_list(v)
                if inner:
                    return inner
    return []


def _find_field_definitions(payload, depth: int = 0) -> list[dict]:
    """Field definitions anywhere in a type definition: dicts with a name and a dataType."""
    if depth > 5:
        return []
    if isinstance(payload, list):
        found = [x for x in payload if isinstance(x, dict) and x.get("name") and x.get("dataType")]
        if found:
            return found
        out = []
        for x in payload:
            out += _find_field_definitions(x, depth + 1)
        return out
    if isinstance(payload, dict):
        out = []
        for v in payload.values():
            if isinstance(v, (dict, list)):
                out += _find_field_definitions(v, depth + 1)
        return out
    return []


def _enum_names(f: dict) -> list[str]:
    values = f.get("enumValues") or f.get("values") or []
    if isinstance(values, dict):
        values = values.get("enumValue", values.get("items", []))
    names = [str(v.get("name") or v.get("localizedLabel")) for v in values if isinstance(v, dict) and (v.get("name") or v.get("localizedLabel"))]
    return names[:50]


def _read_token(r: httpx.Response) -> tuple[str, float, str]:
    """Reads a token response. Returns (token, seconds_valid, problem). The problem says what the
    server actually sent, because "no access_token" covers an OAuth error, an HTML sign-in page and
    a wrong URL alike, and they need different fixes."""
    try:
        body = r.json()
    except ValueError:
        kind = r.headers.get("content-type", "").split(";")[0] or "no content type"
        if "html" in kind:
            return "", 0.0, (f"It answered HTTP {r.status_code} with an HTML page, not JSON: the token URL is "
                             "probably wrong. It should end in /token.")
        return "", 0.0, f"It answered HTTP {r.status_code} with {kind}, not JSON: {_clip(r.text)}"
    if not isinstance(body, dict):
        return "", 0.0, f"It answered HTTP {r.status_code} with {_clip(r.text)}."
    token = body.get("access_token")
    if token:
        return str(token), float(body.get("expires_in") or 3600), ""
    # An OAuth 2.0 error response (RFC 6749 §5.2): "invalid_client" means the id or secret was
    # rejected, "unauthorized_client" that this client may not use client_credentials at all.
    error = str(body.get("error") or "").strip()
    detail = str(body.get("error_description") or body.get("error_message") or "").strip()
    if error or detail:
        hint = {
            "invalid_client": " Check the client ID and secret.",
            "unauthorized_client": " The OAuth provider doesn't allow this client the "
                                   "client_credentials grant; enable it in OpenPages.",
            "invalid_scope": " The scope this client needs wasn't accepted.",
            "invalid_grant": " The OAuth provider rejected the grant.",
        }.get(error, "")
        return "", 0.0, f"It answered HTTP {r.status_code}: {error or 'error'}{' - ' + detail if detail else ''}.{hint}"
    return "", 0.0, f"It answered HTTP {r.status_code} with JSON that has no access_token: {_clip(r.text)}"


def _secure_enough(url: str) -> bool:
    """https anywhere, or plain http on this machine, which is how the tests and local servers run.
    Credentials are only ever sent to a URL that passes this."""
    parsed = urlparse(url)
    return parsed.scheme == "https" or parsed.hostname in ("localhost", "127.0.0.1")


def _clip(text: str, limit: int = 200) -> str:
    return " ".join((text or "").split())[:limit] or "an empty body"


def _short(err: Exception) -> str:
    return (str(err).strip().splitlines() or [type(err).__name__])[0][:200]


def _error_text(r: httpx.Response) -> str:
    try:
        body = r.json()
        if isinstance(body, dict):
            msg = body.get("message") or body.get("errorMessage") or body.get("error")
            if msg:
                return str(msg)[:300]
    except ValueError:
        pass
    return re.sub(r"\s+", " ", r.text)[:300]
