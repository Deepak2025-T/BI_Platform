/**
 * The company's mark and wordmark, drawn rather than loaded.
 *
 * Drawing it keeps it crisp at every size on every screen, costs no network request on the one
 * page a person sees before they are signed in, and lets the sign-in card and the dark panel use
 * the same logo in two colourways without shipping two files.
 */

export const COMPANY_NAME = "Timus Consulting Services";
export const COMPANY_PROMISE = "Technology Simplified!";

interface MarkProps {
  size?: number;
  className?: string;
}

/** The orange tile with the T and its leaf. */
export function TimusMark({ size = 40, className = "" }: MarkProps) {
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 40 40" role="img"
      aria-label={`${COMPANY_NAME} logo`}>
      <defs>
        <linearGradient id="timus-tile" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#FB8C3C" />
          <stop offset="100%" stopColor="#E2600C" />
        </linearGradient>
      </defs>
      <rect width="40" height="40" rx="11" fill="url(#timus-tile)" />
      {/* The T, cut in white so it reads on the tile at sidebar size as well as at hero size. */}
      <g fill="#FFFFFF">
        <rect x="9" y="11" width="22" height="5" rx="2.5" />
        <rect x="17.5" y="11" width="5" height="20" rx="2.5" />
      </g>
      {/* The leaf: the curve the brand turns on, kept at part strength so it reads as a shape
          behind the letter rather than a second letter. */}
      <path d="M16.6 17.6c-.3 6-3.2 10.3-7.8 12.6.3-6.3 3.2-10.6 7.8-12.6z"
        fill="#FFFFFF" opacity=".62" />
    </svg>
  );
}

/**
 * The mark with the name beside it, as it is printed.
 *
 * `onDark` swaps the two inks for white, so the same component serves the sign-in card and the
 * dark panel without a second copy of the logo.
 */
export function TimusWordmark({ size = 40, onDark = false }: { size?: number; onDark?: boolean }) {
  return (
    <div className={"timus-logo" + (onDark ? " on-dark" : "")}>
      <TimusMark size={size} />
      <div className="timus-words">
        <div className="timus-name">TIMUS</div>
        <div className="timus-sub">Consulting Services</div>
        <div className="timus-tag">{COMPANY_PROMISE}</div>
      </div>
    </div>
  );
}

/**
 * The picture on the sign-in panel: a shield over two records.
 *
 * It says what the product is about - something checked, standing in front of the paperwork -
 * in one glance, which is all the time anybody gives a sign-in page.
 */
export function AuthArt({ className = "" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 300 210" fill="none" role="img"
      aria-label="A checked shield in front of two reports">
      <defs>
        <linearGradient id="timus-shield" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#FB8C3C" />
          <stop offset="100%" stopColor="#D9550A" />
        </linearGradient>
      </defs>
      <g transform="rotate(-8 100 110)">
        <rect x="18" y="52" width="118" height="130" rx="12" fill="#FFFFFF" />
        <g fill="#E3E8EE">
          <rect x="36" y="78" width="80" height="7" rx="3.5" />
          <rect x="36" y="96" width="64" height="7" rx="3.5" />
          <rect x="36" y="114" width="74" height="7" rx="3.5" />
          <rect x="36" y="132" width="48" height="7" rx="3.5" />
        </g>
      </g>
      <g transform="rotate(6 196 108)">
        <rect x="140" y="44" width="118" height="130" rx="12" fill="#FFFFFF" />
        <g fill="#E3E8EE">
          <rect x="160" y="70" width="78" height="7" rx="3.5" />
          <rect x="160" y="88" width="58" height="7" rx="3.5" />
          <rect x="160" y="106" width="70" height="7" rx="3.5" />
        </g>
        <rect x="160" y="128" width="46" height="26" rx="6" fill="#DCF0E4" />
      </g>
      <g transform="translate(96 40)">
        <path d="M54 4 100 22v44c0 34-21 59-46 70-25-11-46-36-46-70V22z" fill="url(#timus-shield)" />
        <path d="M34 66l14 15 25-30" stroke="#FFFFFF" strokeWidth="9" strokeLinecap="round"
          strokeLinejoin="round" fill="none" />
      </g>
    </svg>
  );
}
