/**
 * The product's name and mark, in one place.
 *
 * Everything that writes the name reads it from here, so renaming the tool is one edit rather
 * than a search across the app, the login page and the browser tab.
 */

export const PRODUCT_NAME = "OptimusBI";
export const PRODUCT_TAGLINE = "Ask your data";

interface MarkProps {
  size?: number;
  className?: string;
}

/**
 * The mark: three rising bars inside a rounded tile, with a spark over the tallest.
 *
 * It is drawn rather than loaded, so it is crisp at any size, needs no network request, and
 * follows the theme - the bars take the tile's own colour, so it reads on light and dark alike.
 */
export function BrandMark({ size = 34, className = "" }: MarkProps) {
  return (
    <svg className={`brand-mark-svg ${className}`} width={size} height={size} viewBox="0 0 34 34"
      role="img" aria-label={`${PRODUCT_NAME} logo`}>
      <defs>
        <linearGradient id="obi-g" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#22D3EE" />
          <stop offset="100%" stopColor="#0E7490" />
        </linearGradient>
      </defs>
      <rect width="34" height="34" rx="9" fill="url(#obi-g)" />
      {/* The bars are cut out of the tile, so they stay legible whatever sits behind it. */}
      <g fill="#FFFFFF">
        <rect x="8" y="19" width="4" height="8" rx="1.4" opacity="0.75" />
        <rect x="15" y="14" width="4" height="13" rx="1.4" opacity="0.9" />
        <rect x="22" y="9" width="4" height="18" rx="1.4" />
      </g>
      <circle cx="24" cy="6" r="2.6" fill="#FFFFFF" />
    </svg>
  );
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
