#!/usr/bin/env python3
"""Render the startup Mandala (a 9x9 Harada-method chart) from mandala.json.

Outputs (stdlib only, no dependencies):
  mandala/MANDALA.md    Markdown version: 9x9 grid + checklists per pillar
  mandala/index.html    standalone page (full HTML document)
  --fragment PATH       optional: the same page without <html>/<head>/<body>,
                        the format Claude Artifacts expect

Progress: put action numbers (1..8) into a pillar's "ready" list when the
repository already holds a draft for that action, and into "done" when the
founders have actually done it. Then run:  python3 mandala/build.py
"""
import argparse
import html
import json
import pathlib
import re
import urllib.parse

HERE = pathlib.Path(__file__).resolve().parent

# Reading-order positions 0..8 of a 3x3 square; position 4 is the centre.
# The hub (centre block) shows pillar N at the same position as block N.
AROUND = [1, 2, 3, 4, None, 5, 6, 7, 8]

JP_LABEL = "目標達成シート"
REPO_URL = "https://github.com/yk59m2cmhw-hash/u"


def esc(s):
    return html.escape(str(s), quote=True)


VOWELS = set("аеёиоуыэюяaeiouy")
WORD = re.compile(r"[А-Яа-яЁёA-Za-z]{10,}")


def _shy_word(m):
    """Insert soft hyphens at rough Russian syllable breaks (V|CV and C|C) so long words
    can wrap inside narrow cells instead of overflowing them."""
    w = m.group(0)
    low = w.lower()
    out, last = [], 0
    for p in range(3, len(w) - 2):
        a, b, c = low[p - 1], low[p], low[p + 1]
        if b in "ьъй":
            continue
        left_has_v = any(ch in VOWELS for ch in low[:p])
        right_has_v = any(ch in VOWELS for ch in low[p:])
        if not (left_has_v and right_has_v) or p - last < 3:
            continue
        v_cv = a in VOWELS and b not in VOWELS and c in VOWELS
        c_c = a not in VOWELS and b not in VOWELS and a not in "ьъй" and a.isalpha()
        if v_cv or c_c:
            out.append(w[last:p])
            last = p
    out.append(w[last:])
    return "­".join(out)


def shy(s):
    return WORD.sub(_shy_word, s)


def hx(s):
    """Escape for HTML and allow long words to hyphenate."""
    return esc(shy(str(s)))


def load():
    data = json.loads((HERE / "mandala.json").read_text(encoding="utf-8"))
    pillars = data["pillars"]
    assert [p["n"] for p in pillars] == list(range(1, 9)), "pillars must be numbered 1..8"
    for p in pillars:
        assert len(p["actions"]) == 8, f"pillar {p['n']} needs exactly 8 actions"
        p.setdefault("ready", [])
        p.setdefault("done", [])
    return data


def state(p, k):
    if k in p["done"]:
        return "done"
    if k in p["ready"]:
        return "ready"
    return ""


# ---------------------------------------------------------------- Markdown

def render_markdown(data):
    P = {p["n"]: p for p in data["pillars"]}
    g = data["goal"]

    def cell(R, C):
        br, r = divmod(R, 3)
        bc, c = divmod(C, 3)
        b, i = br * 3 + bc, r * 3 + c
        if b == 4:
            if i == 4:
                return f"**ЦЕЛЬ: {g['main']} {g['deadline']}**"
            p = P[AROUND[i]]
            return f"**{p['n']}. {p['name'].upper()}**"
        p = P[AROUND[b]]
        if i == 4:
            return f"**{p['n']}. {p['name'].upper()}**"
        k = AROUND[i]
        mark = {"done": " ✓", "ready": " ◐"}.get(state(p, k), "")
        return f"{p['n']}.{k} {p['actions'][k - 1]}{mark}"

    cols = "ABCDEFGHI"
    out = [
        f"# {data['title']} — 81 клетка",
        "",
        "> Файл собирается из `mandala/mandala.json` скриптом `mandala/build.py`. "
        "Правьте JSON, затем `python3 mandala/build.py`.",
        "",
        f"Метод Харады ({JP_LABEL}, «Open Window 64»): так школьником расписал свою цель "
        "Сёхэй Отани. В центре — цель, вокруг — 8 опор, у каждой опоры — 8 действий. "
        "Номер действия (например, **2.3**) используйте в задачах, коммитах и отчётах.",
        "",
        f"**Цель:** {g['main']} {g['deadline']} — {g['sub']}. Начато {data['started']}.",
        "",
        f"**Принцип:** {data['principle']}",
        "",
        "Отметки: ◐ — в репозитории есть заготовка, ✓ — сделано основателями.",
        "",
        "## Сетка 9×9",
        "",
        "| | " + " | ".join(cols) + " |",
        "|---|" + "---|" * 9,
    ]
    for R in range(9):
        out.append(f"| **{R + 1}** | " + " | ".join(cell(R, C) for C in range(9)) + " |")
    out += ["", "## Опоры и действия", ""]
    for p in data["pillars"]:
        out.append(f"### {p['n']}. {p['name']} — {p['sub']}")
        out.append("")
        for k, a in enumerate(p["actions"], 1):
            st = state(p, k)
            box = "x" if st == "done" else " "
            tail = " *(заготовка в репозитории)*" if st == "ready" else ""
            out.append(f"- [{box}] **{p['n']}.{k}** {a}{tail}")
        out.append("")
    return "\n".join(out)


# -------------------------------------------------------------------- HTML

CSS = r"""
/* Layout: a 9x9 planning sheet (目標達成シート). Heavy ink rules split nine 3x3 blocks;
   the hub block holds the goal, with the 8 pillars in the same positions as their outer
   blocks. Below 1024px the blocks stack, hub first. */
:root{
  --paper:#f4f5fa;
  --sheet:#ffffff;
  --ink:#151b47;
  --ink-soft:#565f8f;
  --rule:#d5daee;
  --frame:#151b47;
  --goal:#1f2c88;
  --goal-ink:#f4f6ff;
  --pillar:#e5e8f7;
  --lit:#fff7d1;
  --marker:#ffe27a;
  --marker-ink:#151b47;
  --ok:#1d7a4f;
  --font-display:"Unbounded","Golos Text",system-ui,sans-serif;
  --font-body:"Golos Text",system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  --font-mono:"JetBrains Mono",ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  --font-jp:"Noto Serif JP","Hiragino Mincho ProN","Yu Mincho",serif;
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --paper:#0a0d20;--sheet:#10142c;--ink:#e8ebff;--ink-soft:#a3aad6;--rule:#252b55;--frame:#9aa4ea;
    --goal:#3445c9;--goal-ink:#ffffff;--pillar:#1a2050;--lit:#231f0b;--marker:#6e5c10;--marker-ink:#fff7d6;
    --ok:#5fd39a;color-scheme:dark;
  }
}
:root[data-theme="dark"]{
  --paper:#0a0d20;--sheet:#10142c;--ink:#e8ebff;--ink-soft:#a3aad6;--rule:#252b55;--frame:#9aa4ea;
  --goal:#3445c9;--goal-ink:#ffffff;--pillar:#1a2050;--lit:#231f0b;--marker:#6e5c10;--marker-ink:#fff7d6;
  --ok:#5fd39a;color-scheme:dark;
}
*{box-sizing:border-box}
body{background:var(--paper);color:var(--ink);font-family:var(--font-body);font-size:15px;line-height:1.5;-webkit-font-smoothing:antialiased}
.page{max-width:1240px;margin:0 auto;display:grid;gap:28px;
  padding-block:clamp(20px,4vw,48px) 56px;
  padding-left:max(16px,env(safe-area-inset-left,0px));
  padding-right:max(16px,env(safe-area-inset-right,0px))}
.head{display:grid;gap:14px}
.eyebrow{display:flex;flex-wrap:wrap;align-items:baseline;gap:6px 14px;font-family:var(--font-mono);font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--ink-soft)}
.eyebrow .jp{font-family:var(--font-jp);font-weight:700;font-size:16px;letter-spacing:.14em;text-transform:none;color:var(--ink)}
h1{margin:0;font-family:var(--font-display);font-weight:700;font-size:clamp(28px,4.4vw,52px);line-height:1.05;letter-spacing:-.01em;text-wrap:balance}
.lede{margin:0;max-width:68ch;color:var(--ink-soft)}
.lede strong{color:var(--ink);font-weight:600}
.fields{margin:0;display:grid;grid-template-columns:repeat(4,minmax(0,1fr));border:2px solid var(--frame);background:var(--sheet)}
.fields div{min-width:0;padding:10px 14px;border-right:1px solid var(--rule)}
.fields div:last-child{border-right:0}
.fields dt{font-family:var(--font-mono);font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--ink-soft)}
.fields dd{margin:2px 0 0;font-weight:600;font-variant-numeric:tabular-nums}
.principle{margin:0;max-width:68ch;font-weight:500}
.principle span{font-family:var(--font-mono);font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--ink-soft);margin-right:8px}

.sheet{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:2px;padding:2px;background:var(--frame)}
.block{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:1px;background:var(--rule);transition:opacity .2s ease}
.block>ol{display:contents;list-style:none;margin:0;padding:0}
.hub{grid-area:2/2}
.goal,.core{grid-area:2/2}
.cell{min-width:0;aspect-ratio:1/1;padding:9px 10px;display:flex;flex-direction:column;gap:6px;background:var(--sheet);
  font-size:clamp(11.5px,1.05vw,12.5px);line-height:1.32;overflow-wrap:break-word;hyphens:manual;
  transition:background-color .2s ease,color .2s ease}
.cell .no{font-family:var(--font-mono);font-size:10.5px;letter-spacing:.04em;color:var(--ink-soft);font-variant-numeric:tabular-nums}
.act .txt{flex:1}
.act.ready .no::after{content:" ◐ заготовка";color:var(--ink-soft)}
.act.done .no::after{content:" ✓ сделано";color:var(--ok)}
.act.done .txt{text-decoration:line-through;text-decoration-thickness:1px;color:var(--ink-soft)}
.core,.pil{margin:0;font:inherit;justify-content:center;align-items:center;text-align:center;background:var(--pillar);color:var(--ink)}
.core .no,.pil .no{font-family:var(--font-display);font-size:13px;font-weight:500;letter-spacing:.04em;color:var(--ink-soft)}
.core .nm,.pil .nm{font-weight:600;font-size:clamp(12px,1.12vw,13.5px);line-height:1.22;text-wrap:balance}
.core .sb,.pil .sb{font-size:11px;line-height:1.25;color:var(--ink-soft)}
.pil{text-decoration:none;cursor:pointer}
.pil:focus-visible{outline:3px solid var(--goal);outline-offset:-3px}
.goal{justify-content:center;align-items:center;text-align:center;gap:3px;background:var(--goal);color:var(--goal-ink)}
.goal .lbl{font-family:var(--font-mono);font-size:10.5px;letter-spacing:.14em;text-transform:uppercase;opacity:.8}
.goal .big{font-family:var(--font-display);font-weight:700;font-size:clamp(14px,1.45vw,19px);line-height:1.05;white-space:nowrap}
.goal .dl{font-family:var(--font-mono);font-size:11px}
.goal .sb{font-size:11px;line-height:1.25;opacity:.9}

.sheet.has-lit .block:not(.hub):not(.is-lit){opacity:.42}
.block.is-lit .cell{background:var(--lit)}
.block.is-lit .core,.pil.is-lit{background:var(--marker);color:var(--marker-ink)}
.block.is-lit .core .no,.block.is-lit .core .sb,.pil.is-lit .no,.pil.is-lit .sb{color:var(--marker-ink)}

.notes{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:20px 28px}
.notes section{min-width:0;display:grid;gap:6px;align-content:start}
.notes h2{margin:0;font-family:var(--font-display);font-weight:500;font-size:15px;letter-spacing:.01em}
.notes p{margin:0;color:var(--ink-soft);max-width:60ch}
.notes code{font-family:var(--font-mono);font-size:12.5px;color:var(--ink)}
.foot{margin:0;padding-top:14px;border-top:1px solid var(--rule);font-size:13px;color:var(--ink-soft)}
.foot a{color:var(--ink);text-underline-offset:3px}
.foot a:focus-visible{outline:2px solid var(--goal);outline-offset:2px}

@media (max-width:1023px){
  .sheet{grid-template-columns:minmax(0,1fr);gap:16px;padding:0;background:transparent}
  .hub{grid-area:auto}
  .block{width:100%;max-width:560px;justify-self:center;border:2px solid var(--frame);scroll-margin-top:16px}
  .cell{aspect-ratio:auto;min-height:116px;font-size:13.5px;padding:10px 11px}
  .core .nm,.pil .nm{font-size:14px}
  .goal .big{font-size:clamp(14px,4vw,20px)}
  .sheet.has-lit .block:not(.hub):not(.is-lit){opacity:1}
}
@media (max-width:800px){.notes{grid-template-columns:minmax(0,1fr)}}
@media (max-width:700px){
  .fields{grid-template-columns:repeat(2,minmax(0,1fr))}
  .fields div:nth-child(2){border-right:0}
  .fields div:nth-child(-n+2){border-bottom:1px solid var(--rule)}
}
@media (max-width:480px){.cell{font-size:12.5px;padding:9px 8px}.core .nm,.pil .nm{font-size:13px}.core .sb,.pil .sb,.goal .sb{font-size:10.5px}}
@media (max-width:380px){.cell{min-height:104px;font-size:12px}}
@media (prefers-reduced-motion:reduce){.block,.cell{transition:none}}
"""

JS = r"""
(function () {
  var sheet = document.querySelector('.sheet');
  if (!sheet) return;
  var blocks = Array.prototype.slice.call(sheet.querySelectorAll('.block[data-p]'));
  var pils = Array.prototype.slice.call(sheet.querySelectorAll('.pil[data-p]'));
  var stacked = window.matchMedia('(max-width: 1023px)');
  var reduce = window.matchMedia('(prefers-reduced-motion: reduce)');
  var pinned = null;
  function light(p) {
    blocks.forEach(function (b) { b.classList.toggle('is-lit', b.dataset.p === p); });
    pils.forEach(function (c) { c.classList.toggle('is-lit', c.dataset.p === p); });
    sheet.classList.toggle('has-lit', !!p);
  }
  function rest() { light(pinned); }
  pils.forEach(function (c) {
    var p = c.dataset.p;
    c.addEventListener('mouseenter', function () { light(p); });
    c.addEventListener('mouseleave', rest);
    c.addEventListener('focus', function () { light(p); });
    c.addEventListener('blur', rest);
    c.addEventListener('click', function (e) {
      e.preventDefault();
      pinned = pinned === p ? null : p;
      light(pinned || p);
      if (stacked.matches) {
        var t = document.getElementById('p' + p);
        if (t) t.scrollIntoView({ behavior: reduce.matches ? 'auto' : 'smooth', block: 'start' });
      }
    });
  });
  blocks.forEach(function (b) {
    var p = b.dataset.p;
    b.addEventListener('mouseenter', function () { light(p); });
    b.addEventListener('mouseleave', rest);
  });
})();
"""


def render_body(data):
    P = {p["n"]: p for p in data["pillars"]}
    g = data["goal"]
    n_ready = sum(len(p["ready"]) for p in data["pillars"])
    n_done = sum(len(p["done"]) for p in data["pillars"])

    hub = ['<section class="block hub" aria-label="Цель и восемь опор">',
           '<div class="cell goal">'
           f'<span class="lbl">{esc(g["label"])}</span>'
           f'<span class="big">{esc(g["main"])}</span>'
           f'<span class="dl">{esc(g["deadline"])}</span>'
           f'<span class="sb">{hx(g["sub"])}</span></div>']
    for i in range(9):
        if i == 4:
            continue
        p = P[AROUND[i]]
        hub.append(f'<a class="cell pil" href="#p{p["n"]}" data-p="{p["n"]}">'
                   f'<span class="no">{p["n"]}</span>'
                   f'<span class="nm">{hx(p["name"])}</span>'
                   f'<span class="sb">{hx(p["sub"])}</span></a>')
    hub.append("</section>")

    blocks = []
    for n in range(1, 9):
        p = P[n]
        items = []
        for k, a in enumerate(p["actions"], 1):
            st = state(p, k)
            cls = f"cell act {st}".strip()
            items.append(f'<li class="{cls}"><span class="no">{p["n"]}.{k}</span>'
                         f'<span class="txt">{hx(a)}</span></li>')
        blocks.append(
            f'<section class="block" id="p{n}" data-p="{n}" aria-labelledby="p{n}-h">'
            f'<h2 class="cell core" id="p{n}-h"><span class="no">{n}</span>'
            f'<span class="nm">{hx(p["name"])}</span><span class="sb">{hx(p["sub"])}</span></h2>'
            f'<ol>{"".join(items)}</ol></section>')

    progress = f"{n_done} из 64" + (f" · заготовок {n_ready}" if n_ready else "")
    return f"""<main class="page" lang="ru">
<header class="head">
<p class="eyebrow"><span class="jp" lang="ja">{JP_LABEL}</span><span>Метод Харады · Open Window 64</span><span>9 × 9 = 81 клетка</span></p>
<h1>{esc(data["title"])}</h1>
<p class="lede">Так школьником расписал свою цель <strong>Сёхэй Отани</strong>: в центре — цель, вокруг — восемь опор, у каждой опоры — восемь конкретных действий. Здесь та же сетка для вашего стартапа. Наведите на опору в центре или нажмите на неё, чтобы подсветить её блок.</p>
<dl class="fields">
<div><dt>Цель</dt><dd>{esc(g["main"])}</dd></div>
<div><dt>Срок</dt><dd>{esc(g["deadline_long"])}</dd></div>
<div><dt>Начато</dt><dd>{esc(data["started"])}</dd></div>
<div><dt>Сделано</dt><dd>{esc(progress)}</dd></div>
</dl>
<p class="principle"><span>Принцип</span>{esc(data["principle"])}</p>
</header>
<div class="sheet">
{"".join(hub)}
{"".join(blocks)}
</div>
<div class="notes">
<section><h2>Как пользоваться</h2><p>Раз в неделю берите в работу 3–5 действий. Цель в центре не меняется, а действие можно заменить, если оно перестало двигать к цели.</p></section>
<section><h2>Номера</h2><p>У каждого действия есть номер, например 2.3. Пишите его в задачах, коммитах и еженедельных отчётах, чтобы видеть, какая опора отстаёт.</p></section>
<section><h2>Прогресс</h2><p>Отметки ставятся в <code>mandala/mandala.json</code>: «ready», когда в репозитории есть заготовка, и «done», когда действие сделано. Затем <code>python3 mandala/build.py</code>.</p></section>
</div>
<p class="foot">Разбор идеи, большие шаги и результаты облачных этапов: <a href="{REPO_URL}">github.com/yk59m2cmhw-hash/u</a></p>
</main>"""


def render_head_bits(data):
    jp = urllib.parse.quote(JP_LABEL)
    return (f'<title>{esc(data["title"])}</title>\n'
            '<meta name="claude:viewport-fit-sides" content="cover">\n'
            '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
            '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
            '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Golos+Text:wght@400;500;600'
            '&family=JetBrains+Mono:wght@400;600&family=Unbounded:wght@500;700&display=swap">\n'
            f'<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Serif+JP:wght@700'
            f'&display=swap&text={jp}">\n'
            f"<style>{CSS}</style>\n")


def render_fragment(data):
    return render_head_bits(data) + render_body(data) + f"\n<script>{JS}</script>\n"


def render_document(data):
    return ('<!doctype html>\n<html lang="ru">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            + render_head_bits(data) + "</head>\n<body>\n" + render_body(data)
            + f"\n<script>{JS}</script>\n</body>\n</html>\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--fragment", help="also write an Artifact-style fragment to this path")
    args = ap.parse_args()
    data = load()
    (HERE / "MANDALA.md").write_text(render_markdown(data) + "\n", encoding="utf-8")
    (HERE / "index.html").write_text(render_document(data), encoding="utf-8")
    if args.fragment:
        pathlib.Path(args.fragment).write_text(render_fragment(data), encoding="utf-8")
    print("wrote MANDALA.md, index.html" + (f", {args.fragment}" if args.fragment else ""))


if __name__ == "__main__":
    main()
