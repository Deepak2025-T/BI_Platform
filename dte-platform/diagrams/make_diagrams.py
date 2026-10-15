"""Generate workflow diagrams (SVG + PNG) in the style of the 'BASIC WORKFLOW' reference image."""
import asyncio, html, pathlib
from playwright.async_api import async_playwright

OUT = pathlib.Path(__file__).parent
W, H = 1400, 720
BLUE, BLUE_B = "#bfdcf7", "#5b6b7c"
CYAN = "#5ff3f3"
ORANGE = "#fcc79a"
GREY = "#c6c6c6"
GREEN = "#c9f0c4"


def esc(s):
    return html.escape(s)


def text_block(x, y, lines, size=13, anchor="middle", weight="normal", lh=None):
    lh = lh or size + 4
    y0 = y - (len(lines) - 1) * lh / 2
    out = []
    for i, ln in enumerate(lines):
        out.append(f'<text x="{x}" y="{y0 + i*lh + size/3:.1f}" font-size="{size}" text-anchor="{anchor}" font-weight="{weight}">{esc(ln)}</text>')
    return "\n".join(out)


class D:
    def __init__(self, title, subtitle):
        self.parts = []
        self.title, self.subtitle = title, subtitle

    def box(self, x, y, w, h, lines, fill=BLUE, rx=2):
        self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{BLUE_B}" stroke-width="2"/>')
        self.parts.append(text_block(x + w / 2, y + h / 2, lines))
        return (x, y, w, h)

    def diamond(self, cx, cy, w, h, lines):
        pts = f"{cx},{cy-h/2} {cx+w/2},{cy} {cx},{cy+h/2} {cx-w/2},{cy}"
        self.parts.append(f'<polygon points="{pts}" fill="{ORANGE}" stroke="{BLUE_B}" stroke-width="2"/>')
        self.parts.append(text_block(cx, cy, lines))

    def note(self, x, y, w, h, lines):
        # grey callout with folded tail pointing down-left, like the reference
        tail = f"M{x+40},{y+h} L{x+60},{y+h+22} L{x+110},{y+h}"
        self.parts.append(f'<path d="M{x},{y} H{x+w} V{y+h} H{x+110} L{x+60},{y+h+22} L{x+40},{y+h} H{x} Z" fill="{GREY}" stroke="#9a9a9a"/>')
        self.parts.append(text_block(x + 10, y + h / 2, lines, size=12, anchor="start", lh=15))

    def arrow(self, pts, label=None, lx=None, ly=None):
        d = "M" + " L".join(f"{a},{b}" for a, b in pts)
        self.parts.append(f'<path d="{d}" fill="none" stroke="#666" stroke-width="2" marker-end="url(#ah)"/>')
        if label:
            self.parts.append(f'<text x="{lx}" y="{ly}" font-size="13">{esc(label)}</text>')

    def legend(self, items, x, y):
        for i, (c, t) in enumerate(items):
            xx = x + i * 210
            self.parts.append(f'<rect x="{xx}" y="{y}" width="18" height="14" fill="{c}" stroke="{BLUE_B}"/>')
            self.parts.append(f'<text x="{xx+26}" y="{y+12}" font-size="12" fill="#333">{esc(t)}</text>')

    def svg(self):
        head = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="Helvetica, Arial, sans-serif">
<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#666"/></marker></defs>
<rect width="{W}" height="{H}" fill="#fff"/>
<rect x="20" y="16" width="{W-40}" height="{H-32}" rx="70" fill="none" stroke="#1f3b8a" stroke-width="2.5"/>
<text x="70" y="78" font-size="28" font-weight="bold">{esc(self.title)}</text>
<text x="70" y="104" font-size="14" fill="#444">{esc(self.subtitle)}</text>
'''
        return head + "\n".join(self.parts) + "\n</svg>"


def etl():
    d = D("AI-POWERED ETL WORKFLOW", "Finance / Accounts domain · PostgreSQL target (any DB, any domain later)")
    y, h, w = 300, 84, 160
    xs = [60, 260, 460, 660, 900, 1150]
    b = [
        d.box(xs[0], y, w, h, ["Upload / connect", "source", "(UI or API)"]),
        d.box(xs[1], y, w, h, ["Extract", "(parse + OCR)"]),
        d.box(xs[2], y, w, h, ["AI Transform", "map to account", "schema"]),
        d.box(xs[3], y, w, h, ["Validate rows", "(types, Dr = Cr,", "duplicates)"]),
        d.box(xs[4], y, 180, h, ["Load to PostgreSQL", "direct SQL or", "REST API"]),
        d.box(xs[5], y, 180, h, ["Auto-forecast", "& check run log", "in UI"]),
    ]
    for i in range(len(b) - 1):
        x1 = b[i][0] + b[i][2]
        d.arrow([(x1, y + h / 2), (b[i + 1][0], y + h / 2)])
    d.note(xs[0] - 10, 140, 200, 110, ["DOCX · PDF · PPTX", "Image (PNG/JPG)", "Excel · CSV · XML", "Each upload = new", "etl_run (audit)"])
    d.note(xs[1] + 30, 140, 180, 110, ["pdfplumber tables", "python-docx / pptx", "Tesseract OCR", "pandas read_excel /", "read_xml"])
    d.note(xs[2] + 30, 140, 200, 110, ["pgvector finds target", "table + columns", "LLM proposes mapping", "(Ollama or Claude)", "Change log kept"])
    d.note(xs[4] + 10, 140, 210, 110, ["Write modes:", "append | upsert", "Batch insert in one", "transaction; rollback", "on error"])
    d.note(xs[5] + 10, 140, 190, 110, ["Monthly revenue /", "expense / cash", "Holt-Winters or", "linear trend", "Stored as forecast"])
    # decision under Validate
    cx = xs[3] + w / 2
    d.diamond(cx, 500, 170, 110, ["All rows", "pass rules?"])
    d.arrow([(cx, y + h), (cx, 445)])
    d.arrow([(cx + 85, 500), (xs[4] + 90, 500), (xs[4] + 90, y + h)], "yes", cx + 100, 492)
    d.arrow([(cx, 555), (cx, 590)], "no", cx + 8, 578)
    d.box(cx - 95, 590, 190, 60, ["Review mapping in UI", "(edit / approve)"], fill=CYAN, rx=8)
    d.arrow([(cx - 95, 620), (xs[2] + w / 2, 620), (xs[2] + w / 2, y + h)], "re-run transform", xs[2] + w / 2 + 8, 612)
    d.legend([(BLUE, "Automatic step"), (ORANGE, "Decision"), (CYAN, "Human-in-the-loop"), (GREY, "Implementation notes")], 70, 665)
    return d


def bi():
    d = D("PROMPT → BI REPORT WORKFLOW", "Agentic RAG over pgvector · LLM mode: Ollama (open source) or Claude (paid) — chosen in Settings")
    y, h, w = 300, 84, 150
    xs = [50, 225, 400, 575, 750, 925, 1100]
    labels = [
        ["Connect DB", "+ index schema", "to pgvector"],
        ["User prompt", "→ intent", "(RAG context)"],
        ["Generate SQL", "(dialect-aware)"],
        ["Validate SQL", "(parse + EXPLAIN)"],
        ["Execute", "read-only,", "row cap"],
        ["Build KPIs +", "charts into", "template"],
    ]
    b = [d.box(xs[i], y, w, h, labels[i]) for i in range(6)]
    b.append(d.box(xs[6], y, 190, h, ["Customize in", "designer &", "publish"]))
    for i in range(len(b) - 1):
        d.arrow([(b[i][0] + b[i][2], y + h / 2), (b[i + 1][0], y + h / 2)])
    d.note(xs[0] - 5, 140, 175, 120, ["PostgreSQL (active)", "MySQL · SQL Server", "Oracle · IBM DB2", "SQLite (next)", "Tables/cols → vectors"])
    d.note(xs[1] + 15, 140, 165, 120, ["Top-k schema chunks", "+ glossary + saved", "examples from", "pgvector", "(cosine search)"])
    d.note(xs[2] + 30, 140, 165, 120, ["Ollama: qwen2.5-", "coder / sqlcoder", "Claude: Sonnet/Haiku", "Prompt = schema +", "few-shot + question"])
    d.note(xs[5] + 15, 140, 170, 120, ["5 templates:", "Executive, Finance,", "Sales, Ops, Table", "Pie · Donut · Line", "Column · Stacked"])
    d.note(xs[6] + 20, 140, 180, 120, ["Drag-drop charts", "Title, colours,", "number format,", "measure, chart type", "Save / publish"])
    # decision under validate
    cx = xs[3] + w / 2
    d.diamond(cx, 500, 170, 110, ["Query valid", "& SELECT-only?"])
    d.arrow([(cx, y + h), (cx, 445)])
    d.arrow([(cx + 85, 500), (xs[4] + w / 2, 500), (xs[4] + w / 2, y + h)], "yes", cx + 100, 492)
    d.arrow([(cx, 555), (cx, 590)], "no", cx + 8, 578)
    d.box(cx - 105, 590, 210, 60, ["Auto-fix: send error", "back to LLM (max 3)"], fill=CYAN, rx=8)
    d.arrow([(cx - 105, 620), (xs[2] + w / 2, 620), (xs[2] + w / 2, y + h)], "retry", xs[2] + w / 2 + 8, 612)
    # feedback loop: published report examples improve RAG
    d.arrow([(xs[6] + 95, y + h), (xs[6] + 95, 560), (xs[6] + 30, 560)])
    d.box(xs[5] - 30, 530, 245, 64, ["Published prompt+SQL pairs saved", "to pgvector as few-shot examples", "(reused in step 2)"], fill=GREEN, rx=8)
    d.legend([(BLUE, "Automatic step"), (ORANGE, "Decision"), (CYAN, "Self-correction loop"), (GREEN, "Learning loop"), (GREY, "Implementation notes")], 70, 665)
    return d


async def render(name, svg):
    (OUT / f"{name}.svg").write_text(svg)
    async with async_playwright() as p:
        br = await p.chromium.launch()
        pg = await br.new_page(viewport={"width": W, "height": H}, device_scale_factor=2)
        await pg.set_content(f"<html><body style='margin:0'>{svg}</body></html>")
        await pg.screenshot(path=str(OUT / f"{name}.png"), full_page=True)
        await br.close()


if __name__ == "__main__":
    asyncio.run(render("etl_workflow", etl().svg()))
    asyncio.run(render("bi_report_workflow", bi().svg()))
    print("done")
