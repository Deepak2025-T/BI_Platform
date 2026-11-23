/**
 * The product's name and mark, in one place.
 *
 * Everything that writes the name reads it from here, so renaming the tool is one edit rather
 * than a search across the app, the login page and the browser tab.
 */

import { TimusMark } from "./Timus";

export const PRODUCT_NAME = "ReportsAI";
export const PRODUCT_TAGLINE = "by Timus Consulting";

interface MarkProps {
  size?: number;
  className?: string;
}

/**
 * The mark: the company's own logo tile.
 *
 * The sidebar, the login page and the browser tab all show the same logo the company prints, so
 * the mark lives in one place (components/Timus) and everything here just points at it.
 */
export function BrandMark({ size = 34, className = "" }: MarkProps) {
  return <TimusMark size={size} className={`brand-mark-svg ${className}`} />;
}

/** The mark and the name together, as the sidebar and the login page show them. */
export default function Brand({ size = 34, sub = PRODUCT_TAGLINE }: { size?: number; sub?: string | null }) {
  return (
    <div className="brand">
      <BrandMark size={size} />
      <div>
        <div className="brand-name">{PRODUCT_NAME}</div>
        {sub && <div className="brand-sub">{sub}</div>}
      </div>
    </div>
  );
}
