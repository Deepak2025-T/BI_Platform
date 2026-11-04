"""
Colour instructions written into a dashboard request.

People say what they want in the prompt: "Use appropriate colours for risk ratings: Minor - Green,
Moderate - Yellow, Significant - Orange, Major - Red." That is read here rather than asked of the
model, because it is a fixed shape, every model would have to be trusted to copy the hex codes
exactly, and a local model that is already slow shouldn't spend a call on it.

The rules go on each chart as style.colorRules, which the dashboard reads when it draws the
categories. A rule for a category a chart doesn't have simply never matches.
"""

import re

# Colours by the names people write, as #RRGGBB. The reporting tones first, because "amber" and
# "red" in a GRC report mean the traffic-light colours, not the CSS ones.
NAMED = {
    "green": "#2E9E5B", "light green": "#7CB342", "lime": "#7CB342", "dark green": "#1E7F4F",
    "yellow": "#E3B505", "amber": "#F5A623", "orange": "#EE7B30", "dark orange": "#D96A1F",
    "red": "#D64545", "dark red": "#9B2226", "crimson": "#9B2226",
    "blue": "#00B4D8", "light blue": "#5BC8E8", "dark blue": "#0D3B66", "navy": "#0D3B66",
    "teal": "#2A9D8F", "cyan": "#00B4D8", "purple": "#6D597A", "violet": "#6D597A",
    "pink": "#D6778F", "brown": "#8D6346", "grey": "#8A98A8", "gray": "#8A98A8",
    "silver": "#C0C0C0", "black": "#1A2332", "white": "#FFFFFF", "gold": "#E3B505",
}

_COLOR = r"#[0-9A-Fa-f]{3,8}|rgba?\s*\([^)]*\)|" + "|".join(sorted((re.escape(n) for n in NAMED), key=len, reverse=True))

# "<name> - <colour>", where the name runs back only as far as the nearest punctuation. Without
# that limit "risk ratings: Minor - Green" would name the category "risk ratings: Minor".
_PAIR = re.compile(
    r"(?:^|[,;:.!?\n(]|\band\b|\bor\b)\s*([^,;:.!?\n()=]{1,40}?)\s*(?:[-‒-―:=]|\bin\b|\bas\b|\bshould be\b)\s*"
    rf"({_COLOR})(?=\s*(?:[,;.\n)]|\band\b|$))",
    re.IGNORECASE)

# Words that are a description of the instruction, never a category to colour.
_NOT_A_CATEGORY = re.compile(
    r"^(and|or|use|using|show|shown|make|set|colou?r|colou?rs|appropriate|all|the|a|an|please|with|for|"
    r"chart|charts|report|reports|dashboard|value|values|rating|ratings|status|statuses|bar|bars|"
    r"pie|line|them|it|this|that|each|every)$", re.IGNORECASE)


def normalize_hex(text: str) -> str:
    """One colour as #RRGGBB, or "" when it isn't one. Mirrors normalizeColor in the frontend."""
    t = text.strip().lower()
    if t in NAMED:
        return NAMED[t]
    # A hex code with or without the "#", the way people paste them out of a style guide.
    if t.startswith("#") or re.fullmatch(r"[0-9a-f]{3,8}", t):
        h = t[1:] if t.startswith("#") else t
        if len(h) in (3, 4):
            return "#" + "".join(c * 2 for c in h[:3]).upper()
        if len(h) in (6, 8):
            return "#" + h[:6].upper()
        return ""
    fn = re.fullmatch(r"rgba?\s*\(([^)]*)\)", t)
    if fn:
        parts = [p for p in re.split(r"[\s,/]+", fn.group(1)) if p][:3]
        if len(parts) != 3:
            return ""
        try:
            numbers = [float(p[:-1]) / 100 * 255 if p.endswith("%") else float(p) for p in parts]
        except ValueError:
            return ""
        return "#" + "".join(f"{max(0, min(255, round(n))):02X}" for n in numbers)
    return ""


def _clean_name(text: str) -> str:
    """The category out of the words before the colour. A sentence runs on into the pair - "Colour
    High as red" - so the words that are plainly part of the instruction are dropped from the
    front, leaving the name itself."""
    words = " ".join(text.split()).strip(" -–—.'\"").split()
    while words and _NOT_A_CATEGORY.match(words[0].strip("'\"")):
        words.pop(0)
    return " ".join(words).strip(" -–—.'\"")


def color_rules_from_prompt(prompt: str) -> list[dict]:
    """The "<category> - <colour>" pairs in a request, in the order they were written.

    Returns [] when the request says nothing about colour, which is the usual case; the dashboard
    then colours by what the category names mean on their own."""
    rules: list[dict] = []
    seen = set()
    for match, color in _PAIR.findall(prompt or ""):
        name = _clean_name(match)
        hex_color = normalize_hex(color)
        # A one-letter name matches far too much, and a bare word of the instruction isn't a
        # category: "Use appropriate colours - Green" names nothing worth colouring.
        if not hex_color or len(name) < 2 or _NOT_A_CATEGORY.match(name):
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        rules.append({"match": name, "color": hex_color})
    return rules[:24]


def apply_color_rules(widgets: list[dict], rules: list[dict]) -> None:
    """Puts the rules on every chart that draws categories, in place. A chart whose categories none
    of the rules name is unaffected when it is drawn, so there is no need to work out which is which
    here - and the query hasn't run yet at this point anyway."""
    if not rules:
        return
    for w in widgets:
        if not isinstance(w, dict) or (w.get("chart") or {}).get("type") in ("kpi", "table", "matrix"):
            continue
        style = dict(w.get("style") or {})
        style.setdefault("colorRules", rules)
        w["style"] = style
