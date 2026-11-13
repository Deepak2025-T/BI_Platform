import { useEffect, useState } from "react";
import { errorMessage } from "../api/client";
import { sharesApi } from "../api/endpoints";
import type { ReportShare } from "../api/types";
import { shortDate } from "../lib/format";
import Modal from "./Modal";

interface Props {
  reportId: number;
  title: string;
  /** Published reports only: a link would otherwise be the thing that makes a draft public. */
  published: boolean;
  onClose: () => void;
}

/** How long a new link should last. Until it is turned off is the honest default for a dashboard
 *  someone is about to embed in a page they maintain. */
const LIFETIMES: [number | null, string][] = [
  [null, "Until I turn it off"],
  [7, "7 days"],
  [30, "30 days"],
  [90, "90 days"],
  [365, "A year"],
];

/** The full address of a link, built in the browser so it carries whatever host people reach the app on. */
const fullUrl = (path: string) => `${window.location.origin}${path}`;

/** The embedded copy asks for ?embed=1, which leaves the header off so the report fills the frame. */
const embedCode = (path: string, width: string, height: string) =>
  `<iframe src="${fullUrl(path)}?embed=1" width="${width}" height="${height}" frameborder="0" `
  + `style="border:0" title="Report" allowfullscreen></iframe>`;

/** One box of text with a button that copies it. */
function CopyBox({ label, text, hint }: { label: string; text: string; hint?: string }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      // Clipboard access is refused on an insecure origin and in some locked-down browsers; the
      // text is on screen and selectable either way, so say what happened rather than nothing.
      setCopied(false);
      return;
    }
    setCopied(true);
    window.setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className="field">
      <span>{label}</span>
      <div className="share-copy">
        <textarea className="share-text" readOnly value={text} rows={text.length > 90 ? 3 : 1}
          aria-label={label} onFocus={(e) => e.currentTarget.select()} />
        <button type="button" className="btn btn-ghost btn-sm" onClick={copy}>{copied ? "Copied" : "Copy"}</button>
      </div>
      {hint && <span className="muted small">{hint}</span>}
    </div>
  );
}

/**
 * The link that opens one report without signing in, and the iframe that embeds it.
 *
 * There is nothing to undo about a link that has been pasted somewhere, so the dialog says in
 * plain words what making one does before it offers the button, and the link is only made when
 * someone asks for it.
 */
export default function ShareDialog({ reportId, title, published, onClose }: Props) {
  const [share, setShare] = useState<ReportShare | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [days, setDays] = useState<number | null>(null);
  const [width, setWidth] = useState("100%");
  const [height, setHeight] = useState("900");

  useEffect(() => {
    if (!published) { setLoading(false); return; }
    sharesApi.get(reportId)
      .then(setShare)
      .catch((e) => setError(errorMessage(e)))
      .finally(() => setLoading(false));
  }, [reportId, published]);

  async function create() {
    setBusy(true);
    setError("");
    try {
      setShare(await sharesApi.create(reportId, days));
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  async function revoke() {
    setBusy(true);
    setError("");
    try {
      await sharesApi.revoke(reportId);
      setShare(null);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title="Share this report" size="lg" onClose={onClose} error={error}
      footer={<button type="button" className="btn" onClick={onClose}>Done</button>}>
      <div className="stack">
        {!published ? (
          <p className="muted">
            Publish <span className="strong" style={{ color: "var(--fg)" }}>{title}</span> first. A link opens the
            report for anyone who has it, so it can&rsquo;t be the thing that makes a draft public.
          </p>
        ) : loading ? (
          <p className="muted">Looking for an existing link…</p>
        ) : share ? (
          <>
            <div className="alert alert-warn small">
              Anyone with this link can see <span className="strong">{title}</span> and its numbers{" "}
              <b>without signing in</b>. Pass it on the way you would the data itself.
            </div>
            <CopyBox label="Link" text={fullUrl(share.path)}
              hint={share.expires_at
                ? `Stops working on ${shortDate(share.expires_at)}.`
                : "Works until you turn it off."} />
            <div className="row-wrap">
              <label className="field" style={{ width: 120 }}>
                <span>Embed width</span>
                <input value={width} onChange={(e) => setWidth(e.target.value)} aria-label="Embed width" />
              </label>
              <label className="field" style={{ width: 120 }}>
                <span>Embed height</span>
                <input value={height} onChange={(e) => setHeight(e.target.value)} aria-label="Embed height" />
              </label>
            </div>
            <CopyBox label="Embed code" text={embedCode(share.path, width, height)}
              hint="Paste this into a page, a wiki or a portal. The report fills the frame and keeps working on its own." />
            <div className="row-between">
              <span className="muted small">
                Made {shortDate(share.created_at)} · {share.views === 0 ? "not opened yet"
                  : `opened ${share.views} time${share.views === 1 ? "" : "s"}`}
                {share.last_viewed_at ? `, last on ${shortDate(share.last_viewed_at)}` : ""}
              </span>
              <button type="button" className="btn btn-ghost btn-sm danger" onClick={revoke} disabled={busy}>
                {busy ? "Turning off…" : "Turn off this link"}
              </button>
            </div>
          </>
        ) : (
          <>
            <p className="muted">
              A link opens <span className="strong" style={{ color: "var(--fg)" }}>{title}</span> for anyone who has
              it, with no sign-in. It shows the charts and their numbers; it never hands over the queries behind them
              or the database they run against, and it can&rsquo;t be used to run a query of its own.
            </p>
            <label className="field" style={{ maxWidth: 240 }}>
              <span>The link lasts</span>
              <select value={days ?? ""} aria-label="How long the link lasts"
                onChange={(e) => setDays(e.target.value ? Number(e.target.value) : null)}>
                {LIFETIMES.map(([value, label]) => (
                  <option key={label} value={value ?? ""}>{label}</option>
                ))}
              </select>
            </label>
            <div>
              <button type="button" className="btn btn-primary" onClick={create} disabled={busy}>
                {busy ? "Making the link…" : "Create share link"}
              </button>
            </div>
          </>
        )}
      </div>
    </Modal>
  );
}
