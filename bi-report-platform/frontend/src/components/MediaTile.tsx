import { useRef, useState } from "react";
import { errorMessage } from "../api/client";
import type { DashboardConfig, Widget } from "../api/types";
import { IMAGE_TYPES, MAX_IMAGE_MB, uploadsApi } from "../api/uploads";
import Icon, { ICON_NAMES } from "./Icon";
import { useToast } from "./Toast";

/**
 * Only http and https are followed. A link typed as "javascript:…" or "data:…" would run in the
 * reader's browser with the app's own privileges, so anything else is dropped rather than shown.
 */
export function safeLink(href: string | undefined): string | null {
  const text = (href ?? "").trim();
  if (!text) return null;
  try {
    const url = new URL(text, window.location.origin);
    return url.protocol === "http:" || url.protocol === "https:" ? url.href : null;
  } catch {
    return null;
  }
}

export type Logo = NonNullable<DashboardConfig["logo"]>;

/** The report's logo, above its title. Shown to readers, and in the printed copy. */
/**
 * How big the logo above a report may be, in pixels of height.
 *
 * 36 is what it has always been. The ceiling is there because the logo sits in the report's title
 * row: past about a hundred it stops being a mark on a report and starts being the report.
 */
export const LOGO_HEIGHT = { default: 36, min: 16, max: 120 };

const logoHeight = (logo?: Logo) =>
  Math.min(LOGO_HEIGHT.max, Math.max(LOGO_HEIGHT.min, logo?.height ?? LOGO_HEIGHT.default));

export function LogoMark({ logo }: { logo?: Logo }) {
  if (!logo?.url) return null;
  const href = safeLink(logo.link);
  const img = <img className="report-logo" src={logo.url} alt="" style={{ height: logoHeight(logo) }} />;
  return href ? <a href={href} target="_blank" rel="noopener noreferrer">{img}</a> : img;
}

/** Puts a logo on the report, or takes it off again. */
export function LogoPicker({ logo, onChange }: { logo?: Logo; onChange: (logo?: Logo) => void }) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);

  async function pick(chosen: File | undefined) {
    if (!chosen) return;
    if (chosen.size > MAX_IMAGE_MB * 1024 * 1024) {
      toast(`That logo is larger than ${MAX_IMAGE_MB} MB.`);
      return;
    }
    setBusy(true);
    try {
      const up = await uploadsApi.image(chosen);
      onChange({ ...logo, url: up.url });
    } catch (err) {
      toast(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <span className="logo-picker no-print">
      <LogoMark logo={logo} />
      <input type="file" accept={IMAGE_TYPES} className="sr-only" id="report-logo"
        onChange={(e) => pick(e.target.files?.[0])} />
      <label className="btn btn-ghost btn-sm" htmlFor="report-logo">
        <Icon name="palette" size={14} />{busy ? "Uploading…" : logo?.url ? "Change logo" : "Add a logo"}
      </label>
      {/* Height alone: the width follows it, so a logo can never be squashed out of shape. It is
          written straight onto the report, which is where the printed and exported copies read
          it from, so what is on screen is what comes out of them. */}
      {logo?.url && (
        <label className="logo-size">
          <span className="muted small">Size</span>
          <input type="range" min={LOGO_HEIGHT.min} max={LOGO_HEIGHT.max} step={2}
            value={logo.height ?? LOGO_HEIGHT.default} aria-label="Logo height"
            title={`${logo.height ?? LOGO_HEIGHT.default}px tall`}
            onChange={(e) => onChange({ ...logo, height: Number(e.target.value) })} />
          <span className="muted small">{logo.height ?? LOGO_HEIGHT.default}px</span>
        </label>
      )}
      {logo?.url && <button className="btn btn-ghost btn-sm" onClick={() => onChange(undefined)}>Remove logo</button>}
    </span>
  );
}

interface Props {
  widget: Widget;
  editable: boolean;
  onChange: (patch: Partial<Widget>) => void;
}

/** A picture or an icon on a dashboard: a logo, a diagram, or a button through to somewhere else. */
export default function MediaTile({ widget: w, editable, onChange }: Props) {
  const toast = useToast();
  const file = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const href = safeLink(w.link);

  async function pick(chosen: File | undefined) {
    if (!chosen) return;
    if (chosen.size > MAX_IMAGE_MB * 1024 * 1024) {
      toast(`That picture is larger than ${MAX_IMAGE_MB} MB.`);
      return;
    }
    setBusy(true);
    try {
      const up = await uploadsApi.image(chosen);
      onChange({ image: up.url, alt: w.alt || up.name.replace(/\.[a-z0-9]+$/i, "") });
    } catch (err) {
      toast(errorMessage(err));
    } finally {
      setBusy(false);
      if (file.current) file.current.value = "";  // so the same file can be chosen again
    }
  }

  const picture = w.image
    ? <img className="media-img" src={w.image} alt={w.alt ?? ""} style={{ maxHeight: w.height ?? 160 }} />
    : w.icon
      ? <Icon name={w.icon} size={Math.min(w.height ?? 64, 96)} className="media-icon" />
      : null;

  if (!editable) {
    if (!picture) return null;
    return href
      ? <a className="media-body" href={href} target="_blank" rel="noopener noreferrer"
           title={`Opens ${href} in a new tab`}>{picture}</a>
      : <div className="media-body">{picture}</div>;
  }

  return (
    <div className="media-edit stack">
      <div className="media-body">{picture ?? <span className="muted small">No picture yet.</span>}</div>
      <div className="row-wrap">
        <input ref={file} type="file" accept={IMAGE_TYPES} className="sr-only" id={`up-${w.id}`}
          onChange={(e) => pick(e.target.files?.[0])} />
        <label className="btn btn-ghost btn-sm" htmlFor={`up-${w.id}`}>
          <Icon name="plus" size={14} />{busy ? "Uploading…" : w.image ? "Replace picture" : "Upload a picture"}
        </label>
        {w.image && <button className="btn btn-ghost btn-sm" onClick={() => onChange({ image: "" })}>Remove</button>}
        <label className="field">
          <span className="sr-only">Icon instead of a picture</span>
          <select value={w.icon ?? ""} aria-label="Icon" onChange={(e) => onChange({ icon: e.target.value })}>
            <option value="">No icon</option>
            {ICON_NAMES.map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
        </label>
      </div>
      <label className="field">Link (optional)
        <input value={w.link ?? ""} placeholder="https://…" onChange={(e) => onChange({ link: e.target.value })} />
        {w.link && !href && <span className="hint note-bad">Only http:// and https:// links open.</span>}
      </label>
      <label className="field">What the picture shows
        <input value={w.alt ?? ""} placeholder="Described for screen readers"
          onChange={(e) => onChange({ alt: e.target.value })} />
      </label>
      <p className="hint">
        Anyone with the picture's address can open it, so don't upload anything confidential.
      </p>
    </div>
  );
}
