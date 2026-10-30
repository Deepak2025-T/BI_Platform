import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { type ChatSummary, type SavedMessage, chatsApi } from "../api/chats";
import { errorMessage } from "../api/client";
import { aiModelsApi, assistantApi } from "../api/endpoints";
import type { AIModelPublic, ChatResult, DataSourceInfo, Widget } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import DataChart from "../components/DataChart";
import Icon from "../components/Icon";
import Modal from "../components/Modal";
import ResultTable from "../components/ResultTable";
import { useToast } from "../components/Toast";
import { rememberModel, rememberedModel } from "../lib/aiModels";
import { shortDate } from "../lib/format";
import { CHART_LABELS, rememberSource, rememberedSource, retype, sourceIdOf, sourceValue } from "../lib/sources";

interface Message {
  id: number;
  question: string;
  status: "pending" | "done" | "error";
  result?: ChatResult;
  error?: string;
}

const toMessage = (m: SavedMessage): Message => ({
  id: m.id, question: m.question, status: m.status === "ok" ? "done" : "error", result: m.result ?? undefined, error: m.error,
});

const EXAMPLES = ["Which tables can I ask about?", "Show the top 10 by total", "How has the total changed by month?"];

/** Chat with a database. Every chat is saved: /chat starts a new one, /chat/:id reopens a saved one. */
export default function Chat() {
  const location = useLocation();
  const navigate = useNavigate();
  const toast = useToast();
  const { isManager } = useAuth();
  const routeId = useParams().id;
  const chatId = routeId ? Number(routeId) : null;
  const start = location.state as { source?: string; model?: string; question?: string } | null;

  const [sources, setSources] = useState<DataSourceInfo[] | null>(null);
  const [models, setModels] = useState<AIModelPublic[] | null>(null);
  const [source, setSource] = useState(start?.source ?? "");
  const [sourceName, setSourceName] = useState(""); // a saved chat's database, even if it was removed since
  const [model, setModel] = useState(start?.model ?? "");
  const [chats, setChats] = useState<ChatSummary[] | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [opening, setOpening] = useState(false);
  const [openError, setOpenError] = useState("");
  const [input, setInput] = useState("");
  const [pinned, setPinned] = useState<number[]>([]);
  const [saving, setSaving] = useState(false);
  const tempId = useRef(-1);
  const createdId = useRef<number | null>(null); // the chat this page just created: don't reload it over the pending answer
  const openChat = useRef(chatId);
  openChat.current = chatId;
  const startedWith = useRef<string | null>(null);
  const bottom = useRef<HTMLDivElement>(null);

  const refreshList = useCallback(() => { chatsApi.list().then(setChats).catch(() => setChats([])); }, []);

  useEffect(() => {
    refreshList();
    assistantApi.sources().then((list) => {
      setSources(list);
      setSource((cur) => {
        if (openChat.current !== null && cur) return cur; // a saved chat keeps its own database
        const ok = (v: string | null) => !!v && list.some((s) => sourceValue(s) === v);
        return ok(cur) ? cur : ok(rememberedSource()) ? rememberedSource()! : sourceValue(list[0]);
      });
    }).catch((e) => { toast(errorMessage(e)); setSources([]); });
    aiModelsApi.available().then(setModels).catch(() => setModels([]));
  }, [toast, refreshList]);

  // Use a model that is turned on: the chat's or the picked one, else the last used, else the default.
  useEffect(() => {
    if (!models) return;
    setModel((cur) => {
      const ok = (v: string | null) => !!v && models.some((m) => String(m.id) === v);
      if (ok(cur)) return cur;
      if (ok(rememberedModel())) return rememberedModel()!;
      return String((models.find((m) => m.is_default) ?? models[0])?.id ?? "");
    });
  }, [models, model]);

  // Open a saved chat, or clear the page for a new one.
  useEffect(() => {
    setPinned([]);
    setOpenError("");
    if (chatId !== null && createdId.current === chatId) return;
    createdId.current = null;
    if (chatId === null) { setMessages([]); setSourceName(""); return; }
    setOpening(true);
    chatsApi.get(chatId).then((c) => {
      setMessages(c.messages.map(toMessage));
      setSource(c.source_id === null ? "builtin" : String(c.source_id));
      setSourceName(c.source_name);
      if (c.model_id !== null) setModel(String(c.model_id));
    }).catch((e) => { setMessages([]); setOpenError(errorMessage(e)); }).finally(() => setOpening(false));
  }, [chatId]);

  // A question typed on the home page is asked as soon as the pickers are ready (once).
  useEffect(() => {
    if (start?.question && chatId === null && source && model && startedWith.current === null) {
      startedWith.current = start.question;
      send(start.question);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [source, model]);

  useEffect(() => { bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [messages]);

  const sourceInfo = sources?.find((s) => sourceValue(s) === source);
  const shownSourceName = sourceInfo?.name ?? sourceName;
  const modelInfo = models?.find((m) => String(m.id) === model);
  const busy = messages.some((m) => m.status === "pending");

  function changeSource(v: string) {
    if (messages.length && !window.confirm("Switch database? This starts a new chat; this one stays in your history.")) return;
    setSource(v);
    rememberSource(v);
    setMessages([]);
    setPinned([]);
    if (chatId !== null) navigate("/chat");
  }

  function changeModel(v: string) {
    setModel(v);
    rememberModel(v);
    if (chatId !== null) chatsApi.update(chatId, { model_id: Number(v) }).catch(() => {});
  }

  async function send(text: string) {
    const question = text.trim();
    if (question.length < 2 || !model || busy) return;
    const temp = tempId.current--;
    setMessages((list) => [...list, { id: temp, question, status: "pending" }]);
    setInput("");
    try {
      let id = chatId;
      if (id === null) {
        // The first question starts a saved chat.
        const created = await chatsApi.start({ source_id: sourceIdOf(source), model_id: Number(model) });
        id = created.id;
        createdId.current = id;
        navigate(`/chat/${id}`, { replace: true });
      }
      const saved = await chatsApi.send(id, question, Number(model));
      setMessages((list) => list.map((m) => (m.id === temp ? toMessage(saved) : m)));
      refreshList();
    } catch (err) {
      setMessages((list) => list.map((m) => (m.id === temp ? { ...m, status: "error", error: errorMessage(err) } : m)));
    }
  }

  function updateResult(id: number, change: (r: Extract<ChatResult, { kind: "result" }>) => Partial<ChatResult>) {
    setMessages((list) => list.map((m) => (m.id === id && m.result?.kind === "result"
      ? { ...m, result: { ...m.result, ...change(m.result) } as ChatResult } : m)));
  }

  const widgetsFrom = (ids: number[]): Widget[] => messages
    .filter((m) => ids.includes(m.id) && m.result?.kind === "result")
    .map((m) => {
      const r = m.result as Extract<ChatResult, { kind: "result" }>;
      return { id: `c${m.id}`, title: r.title, question: m.question, sql: r.sql, chart: r.chart };
    });

  return (
    <div className="chat-layout">
      <ChatHistory chats={chats} current={chatId} onChanged={refreshList}
        onDeleted={(id) => { refreshList(); if (id === chatId) navigate("/chat"); }} />

      <div className="chat-page">
        <header className="chat-head">
          <div>
            <h1 className="h1">Chat with your data</h1>
            <p className="muted small">Every chat is saved in your history. Pin answers to save them together as a report.</p>
          </div>
          <div className="row-wrap">
            <label className="model-picker">
              <span className="muted small">Database</span>
              <select value={source} onChange={(e) => changeSource(e.target.value)} disabled={!sources?.length}>
                {sources?.map((s) => <option key={sourceValue(s)} value={sourceValue(s)}>{s.name} ({s.type_label})</option>)}
                {!sourceInfo && source && sourceName && <option value={source}>{sourceName} (no longer available)</option>}
              </select>
            </label>
            <label className="model-picker">
              <span className="muted small">AI model</span>
              <select value={model} onChange={(e) => changeModel(e.target.value)} disabled={!models?.length}>
                {models?.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
              </select>
            </label>
          </div>
        </header>

        <div className="chat-body">
          {models !== null && models.length === 0 && (
            <div className="alert alert-warn">
              Chat needs an AI model. {isManager ? <Link to="/manage/ai-models">Add one under AI models.</Link> : "Ask a manager to add one."}
            </div>
          )}
          {sources !== null && sources.length === 1 && isManager && chatId === null && (
            <div className="alert alert-info small">
              Only the sample sales data is available. To chat with your own database, add it under <Link to="/manage/connections">Connections</Link> and choose its tables.
            </div>
          )}
          {openError && <div className="alert alert-error">{openError}</div>}
          {opening && <div className="card row-wrap"><span className="spinner" aria-hidden="true" /><span className="muted">Opening the chat…</span></div>}

          {!opening && !openError && messages.length === 0 && (
            <div className="chat-empty stack-sm">
              <div className="strong">Ask about {shownSourceName || "your data"}</div>
              <div className="chip-row">
                {EXAMPLES.map((q) => <button key={q} className="chip-btn" onClick={() => send(q)} disabled={!model}>{q}</button>)}
              </div>
            </div>
          )}

          {messages.map((m) => (
            <div key={m.id} className="chat-turn">
              <div className="chat-question">{m.question}</div>
              {m.status === "pending" && (
                <div className="chat-answer card row-wrap"><span className="spinner" aria-hidden="true" />
                  <span className="muted">{modelInfo?.name ?? "The model"} is writing and checking the query…</span></div>
              )}
              {m.status === "error" && (
                <div className="chat-answer card stack-sm">
                  <div className="alert alert-error">{m.error}</div>
                  <button className="btn btn-ghost btn-sm self-start" onClick={() => send(m.question)} disabled={busy}>Try again</button>
                </div>
              )}
              {m.status === "done" && m.result && (
                <Answer result={m.result} pinned={pinned.includes(m.id)}
                  onPin={() => setPinned((p) => (p.includes(m.id) ? p.filter((x) => x !== m.id) : [...p, m.id]))}
                  onSave={() => { setPinned([m.id]); setSaving(true); }}
                  onRetype={(type) => updateResult(m.id, (r) => ({ chart: retype(r.chart, type, r.columns, r.rows) }))} />
              )}
            </div>
          ))}
          <div ref={bottom} />
        </div>

        <footer className="chat-foot">
          {pinned.length > 0 && (
            <div className="pin-bar">
              <span><b>{pinned.length}</b> answer{pinned.length === 1 ? "" : "s"} pinned</span>
              <button className="btn btn-ghost btn-sm" onClick={() => setPinned([])}>Clear</button>
              <button className="btn btn-primary btn-sm" onClick={() => setSaving(true)}>Save as report</button>
            </div>
          )}
          <form className="chat-compose" onSubmit={(e) => { e.preventDefault(); send(input); }}>
            <label htmlFor="chat-input" className="sr-only">Your question</label>
            <textarea id="chat-input" rows={2} value={input} placeholder={`Ask about ${shownSourceName || "your data"}…`}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(input); } }} />
            <button type="submit" className="btn btn-primary" disabled={busy || !model || opening || input.trim().length < 2}>Send</button>
          </form>
          <p className="muted small">
            {modelInfo?.name ?? "The model"} sees your question, earlier turns in this chat, the shared tables' columns and
            up to 20 result rows. Queries only read data. Enter sends; Shift+Enter adds a line.
          </p>
        </footer>
      </div>

      {saving && (
        <SaveDialog count={pinned.length} defaultTitle={widgetsFrom(pinned)[0]?.title ?? "Chat report"}
          onClose={() => setSaving(false)}
          onSave={async (title) => {
            const report = await assistantApi.save({ source_id: sourceIdOf(source), title, prompt: messages[0]?.question ?? title,
                                                     widgets: widgetsFrom(pinned) });
            toast("Saved as a draft report. Arrange the charts, then publish.");
            navigate(`/reports/${report.id}/edit`);
          }} />
      )}
    </div>
  );
}

/** The saved chats, newest first, with rename and delete. */
function ChatHistory({ chats, current, onChanged, onDeleted }: {
  chats: ChatSummary[] | null; current: number | null; onChanged: () => void; onDeleted: (id: number) => void;
}) {
  const toast = useToast();
  const [editing, setEditing] = useState<number | null>(null);
  const [title, setTitle] = useState("");

  async function rename(id: number) {
    const t = title.trim();
    setEditing(null);
    if (!t) return;
    try { await chatsApi.update(id, { title: t }); onChanged(); } catch (err) { toast(errorMessage(err)); }
  }

  async function remove(c: ChatSummary) {
    if (!window.confirm(`Delete the chat "${c.title}"? Reports saved from it are kept.`)) return;
    try { await chatsApi.remove(c.id); onDeleted(c.id); toast("Chat deleted"); } catch (err) { toast(errorMessage(err)); }
  }

  return (
    <aside className="chat-history" aria-label="Chat history">
      <Link to="/chat" className="btn btn-primary btn-sm new-chat"><Icon name="plus" size={16} />New chat</Link>
      <div className="muted small history-label">History</div>
      {chats === null ? <p className="muted small">Loading…</p> : chats.length === 0 ? (
        <p className="muted small">Your chats will appear here.</p>
      ) : (
        <ul className="history-list">
          {chats.map((c) => (
            <li key={c.id} className={c.id === current ? "on" : ""}>
              {editing === c.id ? (
                <form className="history-rename" onSubmit={(e) => { e.preventDefault(); rename(c.id); }}>
                  <input autoFocus value={title} maxLength={120} aria-label="Chat title"
                    onChange={(e) => setTitle(e.target.value)} onBlur={() => rename(c.id)}
                    onKeyDown={(e) => { if (e.key === "Escape") setEditing(null); }} />
                </form>
              ) : (
                <Link to={`/chat/${c.id}`} className="history-link" aria-current={c.id === current ? "page" : undefined}>
                  <span className="history-title">{c.title}</span>
                  <span className="muted small">{c.source_name} · {c.message_count} question{c.message_count === 1 ? "" : "s"} · {shortDate(c.updated_at)}</span>
                </Link>
              )}
              <span className="history-tools">
                <button className="icon-btn sm" aria-label={`Rename ${c.title}`} title="Rename"
                  onClick={() => { setEditing(c.id); setTitle(c.title); }}><Icon name="edit" size={14} /></button>
                <button className="icon-btn sm danger" aria-label={`Delete ${c.title}`} title="Delete"
                  onClick={() => remove(c)}><Icon name="trash" size={14} /></button>
              </span>
            </li>
          ))}
        </ul>
      )}
    </aside>
  );
}

function Answer({ result, pinned, onPin, onSave, onRetype }: {
  result: ChatResult; pinned: boolean; onPin: () => void; onSave: () => void; onRetype: (t: keyof typeof CHART_LABELS) => void;
}) {
  const [show, setShow] = useState<"" | "table" | "sql" | "tries">("");
  const failedTries = result.attempts.filter((a) => !a.ok).length;
  if (result.kind === "reply") {
    return <div className="chat-answer card"><p className="chat-reply">{result.reply}</p></div>;
  }
  const toggle = (v: typeof show) => setShow((s) => (s === v ? "" : v));
  return (
    <div className={"chat-answer card stack-sm" + (pinned ? " pinned" : "")}>
      <p className="chat-reply">{result.reply}</p>
      <div className="row-between">
        <h3 className="h2">{result.title}</h3>
        <select className="chart-pick" value={result.chart.type} aria-label="Chart type"
          onChange={(e) => onRetype(e.target.value as keyof typeof CHART_LABELS)}>
          {Object.entries(CHART_LABELS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
        </select>
      </div>
      <DataChart columns={result.columns} rows={result.rows} chart={result.chart} height={260} truncated={result.truncated} />
      <div className="row-wrap answer-actions">
        <button className="link-btn" aria-expanded={show === "table"} onClick={() => toggle("table")}>{show === "table" ? "Hide" : "Show"} the rows ({result.row_count}{result.truncated ? "+" : ""})</button>
        <button className="link-btn" aria-expanded={show === "sql"} onClick={() => toggle("sql")}>{show === "sql" ? "Hide" : "Show"} the SQL</button>
        {failedTries > 0 && <button className="link-btn" onClick={() => toggle("tries")}>Fixed after {failedTries} failed {failedTries === 1 ? "try" : "tries"}</button>}
        <span className="grow" />
        <button className={"btn btn-sm " + (pinned ? "btn-primary" : "btn-ghost")} aria-pressed={pinned} onClick={onPin}>
          <Icon name="plus" size={14} />{pinned ? "Pinned" : "Pin to report"}
        </button>
        <button className="btn btn-ghost btn-sm" onClick={onSave}>Save as report</button>
      </div>
      {show === "table" && <ResultTable columns={result.columns} rows={result.rows} truncated={result.truncated} />}
      {show === "sql" && <pre className="code">{result.sql}</pre>}
      {show === "tries" && (
        <ul className="tries">{result.attempts.map((a, i) => <li key={i} className={"note " + (a.ok ? "note-ok" : "note-bad")}>{a.message}</li>)}</ul>
      )}
    </div>
  );
}

function SaveDialog({ count, defaultTitle, onClose, onSave }: {
  count: number; defaultTitle: string; onClose: () => void; onSave: (title: string) => Promise<void>;
}) {
  const [title, setTitle] = useState(defaultTitle);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function save() {
    if (!title.trim()) return;
    setBusy(true);
    setError("");
    try { await onSave(title.trim()); } catch (err) { setError(errorMessage(err)); setBusy(false); }
  }
  return (
    <Modal size="sm" title="Save as report" onClose={onClose} onSubmit={save} error={error}
      footer={<><button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
        <button type="submit" className="btn btn-primary" disabled={busy || !title.trim()}>{busy ? "Saving…" : "Save report"}</button></>}>
      <div className="stack">
        <p className="muted">{count} chart{count === 1 ? "" : "s"} will be saved as a draft dashboard. Each keeps its query, so the
          report shows current data every time it opens.</p>
        <label className="field">Report title
          <input data-autofocus value={title} maxLength={200} onChange={(e) => setTitle(e.target.value)} />
        </label>
      </div>
    </Modal>
  );
}
