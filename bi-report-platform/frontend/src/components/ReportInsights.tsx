import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { errorMessage } from "../api/client";
import { aiModelsApi, assistantApi } from "../api/endpoints";
import type { AIModelPublic, DashboardConfig, Report, Suggestion, Widget, WidgetData } from "../api/types";
import { rememberedModel } from "../lib/aiModels";
import { useSuggestions } from "../lib/suggestions";
import Modal from "./Modal";
import { QuickActions, SuggestionChips } from "./Suggestions";
import { useToast } from "./Toast";

interface Props {
  report: Report & { config: DashboardConfig };
  title: string;
  /** The report is open in its editor: chart suggestions are added to it straight away. */
  editable: boolean;
  canEdit: boolean;
  exporting: "xlsx" | "pptx" | null;
  onExport: (kind: "xlsx" | "pptx") => void;
  onAdded: (widget: Widget, data: WidgetData) => void;
}

/**
 * "Explore more insights" beside a report: what to look at next, from the report's own charts,
 * their SQL and the numbers it last showed, plus what can be done with the report from here.
 *
 * A question goes to chat on the report's database and is asked there; a chart suggestion is
 * added to the report by asking, when the report is open for editing (elsewhere it is asked in
 * chat, where the answer can be pinned onto any report). Nothing runs until something is clicked.
 */
export default function ReportInsights({ report, title, editable, canEdit, exporting, onExport, onAdded }: Props) {
  const navigate = useNavigate();
  const toast = useToast();
  const config = report.config;
  const [models, setModels] = useState<AIModelPublic[] | null>(null);
  const [adding, setAdding] = useState<string | null>(null);
  const [summary, setSummary] = useState<{ summary: string; highlights: string[] } | null>(null);
  const [summarizing, setSummarizing] = useState(false);

  useEffect(() => { aiModelsApi.available().then(setModels).catch(() => setModels([])); }, []);
  const model = models === null ? null
    : models.find((m) => String(m.id) === rememberedModel()) ?? models.find((m) => m.is_default) ?? models[0] ?? null;

  const s = useSuggestions(models === null ? null : `report:${report.id}:${model?.id ?? ""}`, () => ({
    kind: "report", report_id: report.id, model_id: model?.id ?? null }));

  const source = config.source_id === null ? "builtin" : String(config.source_id);
  const toChat = (state: { question?: string; draft?: string }) => navigate("/chat", {
    state: { source, model: model ? String(model.id) : undefined, dataModel: config.data_model ?? null, ...state } });

  async function pick(x: Suggestion) {
    if (x.kind !== "chart" || !editable || !model) { toChat({ question: x.text }); return; }
    setAdding(x.id);
    try {
      const res = await assistantApi.widget({ source_id: config.source_id, model_id: model.id, question: x.text,
                                              data_model: config.data_model ?? null });
      onAdded(res.widget, { id: res.widget.id, ok: true, ...res.data });
      toast(`Added "${res.widget.title}"`);
    } catch (err) {
      toast(errorMessage(err));
    } finally {
      setAdding(null);
    }
  }

  async function action(id: string) {
    if (id === "ask_about") toChat({ draft: `About the "${title}" report: ` });
    else if (id === "add_chart") {
      if (editable) {
        const box = document.getElementById("add-q");
        box?.scrollIntoView({ behavior: "smooth", block: "center" });
        box?.focus();
      } else navigate(`/reports/${report.id}/edit`);
    } else if (id === "compare_periods") {
      toChat({ question: `Compare the main figures in the "${title}" report this period against the previous period` });
    } else if (id === "executive_summary" && model) {
      setSummarizing(true);
      try { setSummary(await assistantApi.summary(report.id, model.id)); }
      catch (err) { toast(errorMessage(err)); }
      finally { setSummarizing(false); }
    } else if (id === "export_excel") onExport("xlsx");
    else if (id === "export_ppt") onExport("pptx");
    else if (id === "build_another") navigate("/", { state: { mode: "build", source } });
  }

  // Exporting and summarising show as busy on their own button.
  const busy = summarizing ? "executive_summary" : exporting === "xlsx" ? "export_excel"
    : exporting === "pptx" ? "export_ppt" : null;
  const actions = (s.data?.actions ?? []).filter((a) => a.id !== "add_chart" || canEdit);

  if (s.dismissed) return null;
  return (
    <section className="report-insights no-print" aria-label="Explore more insights">
      <SuggestionChips title="Explore more insights" items={s.data?.suggestions ?? []}
        loading={s.loading || !!adding} error={s.error} origin={s.data?.origin} notice={s.data?.notice}
        pickHint={editable ? "questions open in chat; charts are added here" : "opens in chat"}
        onPick={pick} onRefresh={s.refresh} onDismiss={s.dismiss} />
      <QuickActions title="Report actions" actions={actions} onAction={action} busy={busy} />
      {summary && (
        <Modal title={`Executive summary: ${title}`} onClose={() => setSummary(null)}
          footer={<button type="button" className="btn" onClick={() => setSummary(null)}>Close</button>}>
          <div className="stack-sm">
            <p className="summary-text">{summary.summary}</p>
            {summary.highlights.length > 0 && (
              <ul className="summary-list">{summary.highlights.map((h) => <li key={h}>{h}</li>)}</ul>
            )}
            <p className="muted small">Written by {model?.name ?? "the AI model"} from the numbers this report last
              showed, without filters. Check the figures against the charts before sharing it.</p>
          </div>
        </Modal>
      )}
    </section>
  );
}
