import { useEffect, useRef } from "react";
import type { DashboardPage } from "../api/types";
import { SwatchRow } from "./Swatches";
import Icon, { ICON_NAMES } from "./Icon";

/** Colours a tab can be given. Strong enough to tell apart in a row of five or six. */
export const TAB_COLORS = ["#00B4D8", "#0D3B66", "#2A9D8F", "#1E7F4F", "#F5A623", "#EE7B30",
                           "#A63D40", "#6D597A", "#8A98A8"];

/** Icons worth putting on a tab: the ones that mean something in a report. */
export const TAB_ICONS = ["home", "grid", "chart", "trend", "reports", "database", "layers",
                          "users", "clock", "bolt", "spark", "question", "info", "check",
                          "palette", "template", "settings"].filter((n) => ICON_NAMES.includes(n));

interface Props {
  page: DashboardPage;
  /** Where this page sits in the tab order, and how many there are, for the move buttons. */
  at: number;
  total: number;
  onChange: (patch: Partial<DashboardPage>) => void;
  onMove: (dir: -1 | 1) => void;
  onRemove?: () => void;
  onClose: () => void;
}

/**
 * Everything about one tab, in one place: its name, its colour, its symbol and where it sits.
 *
 * It opens from the tab itself, so the thing being changed is next to the controls changing it.
 * Each change is saved as it is made rather than on a Done button, because a tab's colour is the
 * kind of thing people try three of before keeping one, and an undo step per try is noise.
 */
export default function PageTabSettings({ page, at, total, onChange, onMove, onRemove, onClose }: Props) {
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === "Escape" : !box.current?.contains(e.target as Node)) onClose();
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => { document.removeEventListener("mousedown", close); document.removeEventListener("keydown", close); };
  }, [onClose]);

  return (
    <div className="tile-menu-list tab-settings" role="dialog" aria-label={`Settings for the tab ${page.name}`} ref={box}>
      <label className="field">Tab name
        <input value={page.name} maxLength={60} autoFocus aria-label="Tab name"
          onChange={(e) => onChange({ name: e.target.value })}
          onKeyDown={(e) => { if (e.key === "Enter") onClose(); }} />
      </label>

      <SwatchRow label="Tab colour" colors={TAB_COLORS} value={page.color} noneLabel="The report's own"
        onChange={(color) => onChange({ color })} />

      <fieldset className="group">
        <legend>Symbol</legend>
        <div className="tab-icons">
          <button type="button" className={"tab-icon" + (!page.icon ? " on" : "")} aria-pressed={!page.icon}
            title="No symbol" aria-label="No symbol" onClick={() => onChange({ icon: undefined })}>
            <span aria-hidden="true">—</span>
          </button>
          {TAB_ICONS.map((name) => (
            <button key={name} type="button" className={"tab-icon" + (page.icon === name ? " on" : "")}
              aria-pressed={page.icon === name} title={name} aria-label={`Symbol: ${name}`}
              onClick={() => onChange({ icon: name })}>
              <Icon name={name} size={15} />
            </button>
          ))}
        </div>
      </fieldset>

      <div className="row-wrap">
        <button type="button" className="btn btn-ghost btn-sm" disabled={at === 0}
          title="Move this tab one to the left" onClick={() => onMove(-1)}>← Move left</button>
        <button type="button" className="btn btn-ghost btn-sm" disabled={at === total - 1}
          title="Move this tab one to the right" onClick={() => onMove(1)}>Move right →</button>
        {onRemove && (
          <button type="button" className="link-btn danger" onClick={onRemove}
            title="Remove this tab. Its tiles move to the first one.">Remove tab</button>
        )}
      </div>
    </div>
  );
}
