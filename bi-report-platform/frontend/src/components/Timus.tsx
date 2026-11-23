/**
 * The company's logo, as it is printed.
 *
 * These are the real files rather than a drawing of them: `timus-mark.png` is the T on its own,
 * cut from the full logo, and `timus-logo.png` is the whole lockup. Both are transparent, so they
 * sit on the white card and on the near-black panel without a box around them.
 *
 * Sizes are given as a height. The width follows from the file's own proportions, so a logo can
 * never arrive squashed.
 */

export const COMPANY_NAME = "Timus Consulting Services";
export const COMPANY_PROMISE = "Technology Simplified!";

/** The T on its own: for the sidebar, the tab icon, and anywhere too narrow for the full logo. */
export function TimusMark({ size = 34, className = "" }: { size?: number; className?: string }) {
  return (
    <img className={`timus-mark ${className}`} src="/timus-mark.png" alt={COMPANY_NAME}
      height={size} style={{ height: size, width: "auto" }} />
  );
}

/** The whole logo - the T, the name and the strap line - as one picture. */
export function TimusWordmark({ size = 44 }: { size?: number }) {
  return (
    <img className="timus-logo" src="/timus-logo.png" alt={`${COMPANY_NAME} - ${COMPANY_PROMISE}`}
      height={size} style={{ height: size, width: "auto" }} />
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
