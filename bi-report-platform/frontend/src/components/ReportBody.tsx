import { useRef, useState } from "react";
import type { QueryResult, ReportConfig, SectionId, SectionSize } from "../api/types";
import { money } from "../lib/format";
import { PALETTES, SECTION_LABELS, buildInsights, monthTotals } from "../lib/report";
import { colsFor } from "../lib/tileSize";
import Icon from "./Icon";
import ResizeHandle from "./ResizeHandle";
import RevenueChart from "./RevenueChart";

/** Sections are full width unless resized; only the revenue chart has a height. */
export const SECTION_HEIGHT = 320;
const hasHeight = (id: SectionId) => id === "revenue";

interface Props {
  title: string;
  result: QueryResult;
  config: ReportConfig;
  /** Editor mode: shows Edit buttons and highlights the selected section */
  selected?: SectionId;
  onSelect?: (id: SectionId) => void;
  /** Editor mode: resizing a section with its corner handle. */
  onResize?: (id: SectionId, size: SectionSize) => void;
}

export default function ReportBody({ title, result, config, selected, onSelect, onResize }: Props) {
  const fmt = config.fmt;
  const grid = useRef<HTMLDivElement>(null);
  const [resizing, setResizing] = useState<SectionId | null>(null);
  return (
    <div className="report-body" ref={grid}>
      {config.sections.map((id) => {
        const size = config.sizes?.[id] ?? {};
        const height = size.height ?? SECTION_HEIGHT;
        return (
        <section key={id} aria-label={SECTION_LABELS[id]}
          className={`card section size-${size.size ?? "auto"}${selected === id ? " is-selected" : ""}${onResize ? " resizable" : ""}${resizing === id ? " resizing" : ""}`}>
          <div className="section-head">
            <h2 className="h2">{id === "revenue" ? title : SECTION_LABELS[id]}</h2>
            {onSelect && (
              <button className="btn btn-ghost btn-sm" onClick={() => onSelect(id)} aria-pressed={selected === id}>
                {selected === id ? "Editing" : "Edit"}
              </button>
            )}
          </div>
          {id === "kpis" && <Kpis result={result} fmt={fmt} />}
          {id === "revenue" && (
            <RevenueChart result={result} kind={config.chart} palette={config.palette} fmt={fmt} showValues={config.showValues}
              height={height} />
          )}
          {id === "products" && <Products result={result} config={config} />}
          {id === "insights" && <Insights result={result} config={config} />}
          {onResize && (
            <ResizeHandle name={SECTION_LABELS[id]} cols={colsFor(size.size, 12)} height={hasHeight(id) ? height : undefined}
              grid={grid} onChange={(patch) => onResize(id, patch)} onActive={(on) => setResizing(on ? id : null)} />
          )}
        </section>
        );
      })}
    </div>
  );
}

function Kpis({ result, fmt }: { result: QueryResult; fmt: ReportConfig["fmt"] }) {
  const [open, setOpen] = useState<string | null>(null);
  const totals = monthTotals(result);
  const best = totals.indexOf(Math.max(...totals));
  const regionTotals = result.regions
    .map((r) => ({ r, v: result.series[r].reduce((a, b) => a + b, 0) }))
    .sort((a, b) => b.v - a.v);
  const top = result.products[0];
  const where = `From ${result.source}, ${result.period_short}`;

  const tiles = [
    { id: "total", label: `Total ${result.measure_label.toLowerCase()}`, value: money(result.total, fmt),
      sub: result.compare ? `${result.compare.pct >= 0 ? "+" : ""}${result.compare.pct}% ${result.compare.label}` : result.period_short,
      how: `Sum of ${result.measure_label.toLowerCase()} across the period.` },
    { id: "region", label: "Top region", value: regionTotals[0]?.r ?? "None", sub: regionTotals[0] ? money(regionTotals[0].v, fmt) : "",
      how: "Region with the highest total." },
    { id: "month", label: "Best month", value: result.months[best] ?? "None", sub: money(totals[best] ?? 0, fmt),
      how: "Month with the highest total." },
    { id: "product", label: "Top product", value: top?.name ?? "None", sub: top ? money(top.value, fmt) : "",
      how: "Product with the highest total." },
  ];

  return (
    <div className="kpi-grid">
      {tiles.map((t) => (
        <div key={t.id} className="kpi">
          <div className="kpi-top">
            <span className="kpi-label">{t.label}</span>
            <button className="icon-btn" aria-label="Where this number comes from" aria-expanded={open === t.id}
              onClick={() => setOpen(open === t.id ? null : t.id)}>
              <Icon name="info" size={16} />
            </button>
          </div>
          <div className="kpi-value">{t.value}</div>
          <div className="kpi-sub">{t.sub}</div>
          {open === t.id && (
            <div className="kpi-source">
              <div>{t.how}</div>
              <div className="muted small">{where}. Query ran in {result.elapsed_ms} ms.</div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function Products({ result, config }: { result: QueryResult; config: ReportConfig }) {
  const items = result.products.slice(0, config.topN);
  const max = items[0]?.value || 1;
  const colors = PALETTES[config.palette].colors;
  return (
    <div className="products">
      {items.map((p, i) => (
        <div key={p.name} className="product-row">
          <div className="product-name">{p.name}</div>
          <div className="bar-track"><div className="bar-fill" style={{ width: `${(p.value / max) * 100}%`, background: i === 0 ? colors[1] : colors[0] }} /></div>
          <div className="product-val">{money(p.value, config.fmt)}</div>
        </div>
      ))}
    </div>
  );
}

function Insights({ result, config }: { result: QueryResult; config: ReportConfig }) {
  const items = buildInsights(result, config.fmt);
  if (!items.length) return <p className="muted">Not enough data in this view to compare. Try widening the filters.</p>;
  return (
    <>
      <ul className="insights">
        {items.map((i) => (
          <li key={i.text}>
            <span>{i.text}</span>
            <span className="muted small">Based on {i.basis}</span>
          </li>
        ))}
      </ul>
      <p className="muted small">Calculated from the numbers in this report only.</p>
    </>
  );
}
