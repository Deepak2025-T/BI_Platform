import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { type ChatSummary, type SavedMessage, chatsApi } from "../api/chats";
import { errorMessage } from "../api/client";
import { aiModelsApi, assistantApi, dataModelsApi } from "../api/endpoints";
import type { AIModelPublic, ChartType, ChatResult, DataModelSummary, DataSourceInfo, SuggestionRequest, Widget } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import DataChart from "../components/DataChart";
import Dictate from "../components/Dictate";
import Modal from "../components/Modal";
import PalettePicker from "../components/PalettePicker";
import Icon from "../components/Icon";
import AddToReport from "../components/AddToReport";
import ResultTable from "../components/ResultTable";
import { QuickActions, SuggestionChips } from "../components/Suggestions";
import { useToast } from "../components/Toast";
import { downloadCsv, shownUnder, useSuggestions } from "../lib/suggestions";
import { rememberModel, rememberedModel } from "../lib/aiModels";
import { bySolution, rememberModel as rememberDataModel, rememberedModel as rememberedDataModel } from "../lib/dataModel";
import { appendSpoken } from "../lib/dictation";
import { shortDate } from "../lib/format";
import { CHART_LABELS, cannotDraw, rememberSource, rememberedSource, retype, sourceIdOf, sourceValue } from "../lib/sources";

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
  // `question` is asked as soon as the pickers are ready; `draft` only fills the box.
  const start = location.state as { source?: string; model?: string; question?: string; draft?: string;
                                    dataModel?: string | null } | null;

  const [sources, setSources] = useState<DataSourceInfo[] | null>(null);
  const [models, setModels] = useState<AIModelPublic[] | null>(null);
  const [source, setSource] = useState(start?.source ?? "");
  const [sourceName, setSourceName] = useState(""); // a saved chat's database, even if it was removed since
  const [model, setModel] = useState(start?.model ?? "");
  // The OpenPages object model this chat is held to. Fixed once the chat has started, because
  // every answer in it was written against those object types.
  const [dataModel, setDataModel] = useState(start?.dataModel ?? "");
  const [dataModels, setDataModels] = useState<DataModelSummary[]>([]);
  const [chats, setChats] = useState<ChatSummary[] | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [opening, setOpening] = useState(false);
  const [openError, setOpenError] = useState("");
  const [input, setInput] = useState(start?.draft ?? "");
  const [pinned, setPinned] = useState<number[]>([]);
  const [saving, setSaving] = useState(false);
  const tempId = useRef(-1);
  const createdId = useRef<number | null>(null); // the chat this page just created: don't reload it over the pending answer
  const startedChat = useRef<number | null>(null); // a chat started but not yet answered, so a retry reuses it
  const openChat = useRef(chatId);
  openChat.current = chatId;
  const startedWith = useRef<string | null>(null);
  const shownChat = useRef<number | null | undefined>(undefined); // undefined: nothing shown yet
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
    dataModelsApi.list().then(setDataModels).catch(() => setDataModels([]));
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
    // The chat this ran for last time. The page is only cleared when moving from a saved chat to a
    // new one: clearing on every run would also wipe a question just sent from the home page,
    // because React runs this twice on the first render in development (StrictMode), after the
    // question below has already been asked.
    const previous = shownChat.current;
    shownChat.current = chatId;
    setPinned([]);
    setOpenError("");
    if (chatId !== null && createdId.current === chatId) return;
    createdId.current = null;
    if (chatId === null) {
      if (previous !== undefined && previous !== null) {
        setMessages([]); setSourceName(""); startedChat.current = null;
      }
      return;
    }
    setOpening(true);
    chatsApi.get(chatId).then((c) => {
      setMessages(c.messages.map(toMessage));
      setSource(c.source_id === null ? "builtin" : String(c.source_id));
      setSourceName(c.source_name);
      setDataModel(c.data_model || "");
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
  // Only OpenPages has an object model, so the picker and what it sends are both conditional.
  const isOpenPages = sourceInfo?.db_type === "openpages";
  const dataModelSent = isOpenPages && dataModel ? dataModel : null;
  const shownSourceName = sourceInfo?.name ?? sourceName;
  const modelInfo = models?.find((m) => String(m.id) === model);
  const busy = messages.some((m) => m.status === "pending");

  function changeSource(v: string) {
    if (messages.length && !window.confirm("Switch database? This starts a new chat; this one stays in your history.")) return;
    setSource(v);
    rememberSource(v);
    setMessages([]);
    setPinned([]);
    setDataModel(rememberedDataModel(v));
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
      // A chat started for a question that then failed is reused by "Try again", so a retry doesn't
      // leave an empty chat behind in the history every time.
      let id = chatId ?? startedChat.current;
      let started = false;
      if (id === null) {
        // The first question starts a saved chat.
        const created = await chatsApi.start({ source_id: sourceIdOf(source), model_id: Number(model),
                                               data_model: dataModelSent });
        id = created.id;
        createdId.current = id;
        startedChat.current = id;
        started = true;
      }
      const saved = await chatsApi.send(id, question, Number(model));
      setMessages((list) => list.map((m) => (m.id === temp ? toMessage(saved) : m)));
      // Only now does the page become /chat/<id>. A local model can take minutes to answer, and
      // until it has, that chat holds no message: moving there first means anything that re-reads
      // it - the page being reloaded while waiting, most of all - replaces the question being
      // asked with an empty chat, and the question looks lost although the answer is still coming.
      if (started) navigate(`/chat/${id}`, { replace: true });
      refreshList();
    } catch (err) {
      setMessages((list) => list.map((m) => (m.id === temp ? { ...m, status: "error", error: errorMessage(err) } : m)));
    }
  }

  function updateResult(id: number, change: (r: Extract<ChatResult, { kind: "result" }>) => Partial<ChatResult>) {
    setMessages((list) => list.map((m) => (m.id === id && m.result?.kind === "result"
      ? { ...m, result: { ...m.result, ...change(m.result) } as ChatResult } : m)));
  }

  // The palette every answer here is drawn with, and that pinned charts carry onto a report.
  // Remembered, because a palette is a house style rather than a per-question choice.
  const [palette, setPalette] = useState<string[] | undefined>(() => {
    try { const saved = localStorage.getItem("chartPalette"); return saved ? JSON.parse(saved) : undefined; }
    catch { return undefined; }
  });
  const choosePalette = (next: string[] | undefined) => {
    setPalette(next);
    try { next ? localStorage.setItem("chartPalette", JSON.stringify(next)) : localStorage.removeItem("chartPalette"); }
    catch { /* a browser with storage switched off still gets the palette for this visit */ }
  };
  const [palettePanel, setPalettePanel] = useState(false);

  const widgetsFrom = (ids: number[]): Widget[] => messages
    .filter((m) => ids.includes(m.id) && m.result?.kind === "result")
    .map((m) => {
      const r = m.result as Extract<ChatResult, { kind: "result" }>;
      return { id: `c${m.id}`, title: r.title, question: m.question, sql: r.sql, chart: r.chart,
               ...(palette?.length ? { style: { palette } } : {}) };
    });

  // Suggestions: starters for an empty chat, follow-ups under the newest answer. Each is fetched
  // once (lib/suggestions), and nothing shown or asked in this chat is suggested again.
  const modelSent = model ? Number(model) : null;
  const asked = messages.map((m) => m.question);
  const followKeys = messages.filter((m) => m.id > 0).map((m) => `followup:${m.id}`);
  const starterKey = !opening && !openError && messages.length === 0 && source && models !== null && (!!model || models.length === 0)
    ? `starter:${source}:${dataModelSent ?? ""}:${modelSent ?? ""}` : null;
  const starters = useSuggestions(starterKey, () => ({
    kind: "starter", source_id: sourceIdOf(source), data_model: dataModelSent, model_id: modelSent }));
  const latest = [...messages].reverse().find((m) => m.status === "done" && m.result && m.id > 0);
  const followupRequest = (m: Message) => (): SuggestionRequest => {
    const r = m.result!;
    const base = { kind: "followup" as const, source_id: sourceIdOf(source), data_model: dataModelSent,
                   model_id: modelSent, question: m.question, answer: r.reply,
                   asked, previous: shownUnder([...followKeys, ...(starterKey ? [starterKey] : [])]) };
    return r.kind === "result"
      ? { ...base, title: r.title, sql: r.sql, columns: r.columns, rows: r.rows.slice(0, 5), row_count: r.row_count }
      : base;
  };
  const fillInput = (text: string) => {
    setInput(text);
    requestAnimationFrame(() => document.getElementById("chat-input")?.focus());
  };

  return (
    <div className="chat-layout">
      <ChatHistory chats={chats} current={chatId} onChanged={refreshList}
        onDeleted={(id) => { refreshList(); if (id === chatId) navigate("/chat"); }} />

      <div className="chat-page">
        <header className="chat-head">
          <div>
            <h1 className="h1">Chat with your data</h1>
            <p className="muted small">Every chat is saved in your history. Pin answers to put them on a report — a new one, or one you already have.</p>
          </div>
          <div className="row-wrap">
            <label className="model-picker">
              <span className="muted small">Database</span>
              <select value={source} onChange={(e) => changeSource(e.target.value)} disabled={!sources?.length}>
                {sources?.map((s) => <option key={sourceValue(s)} value={sourceValue(s)}>{s.name} ({s.type_label})</option>)}
                {!sourceInfo && source && sourceName && <option value={source}>{sourceName} (no longer available)</option>}
              </select>
            </label>
            {isOpenPages && dataModels.length > 0 && (
              <label className="model-picker">
                <span className="muted small">Data model</span>
                <select value={dataModel} aria-label="OpenPages data model"
                  onChange={(e) => { setDataModel(e.target.value); rememberDataModel(source, e.target.value); }}
                  disabled={messages.length > 0}
                  title={messages.length > 0 ? "The model is fixed once a chat has started. Start a new chat to change it."
                    : "Which object types this chat may use, and how they join."}>
                  <option value="">Every shared object type</option>
                  {bySolution(dataModels).map(([solution, list]) => (
                    <optgroup key={solution} label={solution}>
                      {list.map((m) => <option key={m.key} value={m.key}>{m.namespace}{m.is_default ? " (default)" : ""}</option>)}
                    </optgroup>
                  ))}
                </select>
              </label>
            )}
            <button type="button" className="btn btn-ghost" onClick={() => setPalettePanel(true)}>Colour palette</button>
            <label className="model-picker">
              <span className="muted small">AI model</span>
              <select value={model} onChange={(e) => changeModel(e.target.value)} disabled={!models?.length}>
                {models?.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
              </select>
            </label>
          </div>
        </header>

        {palettePanel && (
          <Modal title="Colour palette" size="lg" onClose={() => setPalettePanel(false)}
            footer={<button type="button" className="btn" onClick={() => setPalettePanel(false)}>Done</button>}>
            <PalettePicker value={palette} onChange={choosePalette}
              hint="Used for every answer here, and kept when you pin one onto a report." />
          </Modal>
        )}

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
              {!starters.dismissed && (
                <SuggestionChips title="Questions to start with" items={starters.data?.suggestions ?? []}
                  loading={starters.loading} error={starters.error} origin={starters.data?.origin}
                  notice={starters.data?.notice} pickHint="fills the box" disabled={!model}
                  onPick={(s) => fillInput(s.text)} onRefresh={starters.refresh} onDismiss={starters.dismiss} />
              )}
              {(starters.dismissed || (!starters.loading && !starters.data?.suggestions.length)) && (
                <div className="chip-row">
                  {EXAMPLES.map((q) => <button key={q} className="chip-btn" onClick={() => fillInput(q)} disabled={!model}>{q}</button>)}
                </div>
              )}
            </div>
          )}

          {messages.map((m) => (
            <div key={m.id} className="chat-turn">
              <div className="chat-question">{m.question}</div>
              {m.status === "pending" && (
                <div className="chat-answer card stack-sm">
                  <div className="row-wrap"><span className="spinner" aria-hidden="true" />
                    <span className="muted">{modelInfo?.name ?? "The model"} is writing and checking the query…</span></div>
                  <span className="muted small">A model running on this machine can take a few minutes. Leaving the
                    page stops the answer being shown, though it is still saved to this chat.</span>
                </div>
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
                  palette={palette}
                  onRetype={(type) => updateResult(m.id, (r) => ({ chart: retype(r.chart, type, r.columns, r.rows) }))}
                  followup={m === latest ? {
                    suggestKey: `followup:${m.id}`, build: followupRequest(m), disabled: busy || !model,
                    onAsk: send,
                    onAction: (id, title) => {
                      if (id === "compare_period") send(`Compare ${title} with the previous period`);
                      else if (id === "build_report") {
                        navigate("/", { state: { mode: "build", source,
                          prompt: `Build a report around this question: ${m.question}` } });
                      }
                    },
                  } : undefined} />
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
              <button className="btn btn-primary btn-sm" onClick={() => setSaving(true)}>Add to a report</button>
            </div>
          )}
          <form className="chat-compose" onSubmit={(e) => { e.preventDefault(); send(input); }}>
            <label htmlFor="chat-input" className="sr-only">Your question</label>
            <textarea id="chat-input" rows={2} value={input} placeholder={`Ask about ${shownSourceName || "your data"}…`}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(input); } }} />
            <Dictate compact what="your question" onPhrase={(said) => setInput((q) => appendSpoken(q, said))} />
            <button type="submit" className="btn btn-primary" disabled={busy || !model || opening || input.trim().length < 2}>Send</button>
          </form>
          <p className="muted small">
            {modelInfo?.name ?? "The model"} sees your question, earlier turns in this chat, the shared tables' columns and
            up to 20 result rows. Queries only read data. Enter sends; Shift+Enter adds a line.
          </p>
        </footer>
      </div>

      {saving && (
        <AddToReport sourceId={sourceIdOf(source)} sourceName={sourceName || "this database"}
          widgets={widgetsFrom(pinned)} defaultTitle={widgetsFrom(pinned)[0]?.title ?? "Chat report"}
          prompt={messages[0]?.question ?? ""}
          onClose={() => setSaving(false)}
          onDone={(report, created) => {
            toast(created ? "Saved as a draft report. Arrange the charts, then publish."
                          : `Added to "${report.title}".`);
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

interface FollowUpProps {
  suggestKey: string;
  build: () => SuggestionRequest;
  disabled: boolean;
  /** Asks a suggestion straight away, as if it had been typed. */
  onAsk: (text: string) => void;
  /** Quick actions the page handles; the answer handles its own (rows, SQL, chart type, export). */
  onAction: (id: string, title: string) => void;
}

/** "Suggested follow-up questions" and the quick actions that apply, under the newest answer. */
function FollowUps({ suggestKey, build, disabled, onAsk, onAction, pressed }: FollowUpProps & {
  onAction: (id: string) => void; pressed: string[];
}) {
  const s = useSuggestions(suggestKey, build);
  if (s.dismissed) return null;
  return (
    <div className="chat-followups">
      <SuggestionChips title="Suggested follow-up questions" items={s.data?.suggestions ?? []}
        loading={s.loading} error={s.error} origin={s.data?.origin} notice={s.data?.notice}
        disabled={disabled} pickHint="asks it" onPick={(x) => onAsk(x.text)}
        onRefresh={s.refresh} onDismiss={s.dismiss} />
      <QuickActions actions={s.data?.actions ?? []} onAction={onAction} pressed={pressed} />
    </div>
  );
}

function Answer({ result, pinned, palette, onPin, onSave, onRetype, followup }: {
  result: ChatResult; pinned: boolean; palette?: string[]; onPin: () => void; onSave: () => void; onRetype: (t: keyof typeof CHART_LABELS) => void;
  followup?: FollowUpProps;
}) {
  const [show, setShow] = useState<"" | "table" | "sql" | "tries" | "charts">("");
  const failedTries = result.attempts.filter((a) => !a.ok).length;
  if (result.kind === "reply") {
    return (
      <div className="chat-answer card">
        <p className="chat-reply">{result.reply}</p>
        {followup && <FollowUps {...followup} onAction={(id) => followup.onAction(id, "")} pressed={[]} />}
      </div>
    );
  }
  const quick = (id: string) => {
    if (id === "view_rows") toggle("table");
    else if (id === "view_sql") toggle("sql");
    else if (id === "change_chart") toggle("charts");
    else if (id === "export_csv") downloadCsv(result.title, result.columns, result.rows);
    else if (id === "add_to_report") onSave();
    else followup?.onAction(id, result.title);
  };
  const pressed = [show === "table" && "view_rows", show === "sql" && "view_sql", show === "charts" && "change_chart"]
    .filter(Boolean) as string[];
  const toggle = (v: typeof show) => setShow((s) => (s === v ? "" : v));
  return (
    <div className={"chat-answer card stack-sm" + (pinned ? " pinned" : "")}>
      <p className="chat-reply">{result.reply}</p>
      <div className="row-between">
        <h3 className="h2">{result.title}</h3>
        <select className="chart-pick" value={result.chart.type} aria-label="Chart type"
          onChange={(e) => onRetype(e.target.value as keyof typeof CHART_LABELS)}>
          {Object.entries(CHART_LABELS).map(([k, l]) => {
            const no = cannotDraw(k as ChartType, result.columns, result.rows);
            return <option key={k} value={k} disabled={!!no} title={no}>{no ? `${l} — ${no.toLowerCase()}` : l}</option>;
          })}
        </select>
      </div>
      <DataChart columns={result.columns} rows={result.rows} chart={result.chart} style={{ palette }}
        height={260} truncated={result.truncated} />
      <div className="row-wrap answer-actions">
        <button className="link-btn" aria-expanded={show === "table"} onClick={() => toggle("table")}>{show === "table" ? "Hide" : "Show"} the rows ({result.row_count}{result.truncated ? "+" : ""})</button>
        <button className="link-btn" aria-expanded={show === "sql"} onClick={() => toggle("sql")}>{show === "sql" ? "Hide" : "Show"} the SQL</button>
        {failedTries > 0 && <button className="link-btn" onClick={() => toggle("tries")}>Fixed after {failedTries} failed {failedTries === 1 ? "try" : "tries"}</button>}
        <span className="grow" />
        <button className={"btn btn-sm " + (pinned ? "btn-primary" : "btn-ghost")} aria-pressed={pinned} onClick={onPin}>
          <Icon name="plus" size={14} />{pinned ? "Pinned" : "Pin to report"}
        </button>
        <button className="btn btn-ghost btn-sm" onClick={onSave}>Add to a report</button>
      </div>
      {show === "table" && <ResultTable columns={result.columns} rows={result.rows} truncated={result.truncated} />}
      {show === "sql" && <pre className="code">{result.sql}</pre>}
      {show === "tries" && (
        <ul className="tries">{result.attempts.map((a, i) => <li key={i} className={"note " + (a.ok ? "note-ok" : "note-bad")}>{a.message}</li>)}</ul>
      )}
      {show === "charts" && (
        <div className="chip-row" role="group" aria-label="Chart type">
          {Object.entries(CHART_LABELS).map(([k, l]) => {
            const no = cannotDraw(k as ChartType, result.columns, result.rows);
            return no ? null : (
              <button key={k} type="button" className={"chip-btn" + (result.chart.type === k ? " on" : "")}
                aria-pressed={result.chart.type === k} onClick={() => onRetype(k as keyof typeof CHART_LABELS)}>{l}</button>
            );
          })}
        </div>
      )}
      {followup && <FollowUps {...followup} onAction={quick} pressed={pressed} />}
    </div>
  );
}
