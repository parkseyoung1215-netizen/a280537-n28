"""Draw a design as one HTML page: front view with shelf heights, the cut list,
and how the parts sit on each sheet (so the store knows how to cut).

Usage: python3 render.py spec.json out.html
"""
import html
import json
import sys

from furniture import Spec, design, MATERIALS, SHEET


def front_view(r, scale):
    s = r.spec
    W, H, t = s["width"], s["height"], s["thickness"]
    pad = 60
    w, h = W * scale, H * scale
    svg = [f'<svg viewBox="0 0 {w + 2 * pad + 80} {h + 2 * pad}" class="draw" role="img" aria-label="Front view">']
    x0, y0 = pad, pad
    def rect(x, y, rw, rh, cls):
        svg.append(f'<rect x="{x0 + x * scale:.1f}" y="{y0 + (H - y - rh) * scale:.1f}" '
                   f'width="{rw * scale:.1f}" height="{rh * scale:.1f}" class="{cls}"/>')
    rect(0, 0, W, H, "back")
    rect(0, 0, t, H, "board")
    rect(W - t, 0, t, H, "board")
    rect(t, 0, W - 2 * t, t, "board")
    rect(t, H - t, W - 2 * t, t, "board")
    for top in r.shelf_positions:
        rect(t, top - t, W - 2 * t, t, "board")
        y = y0 + (H - top) * scale
        svg.append(f'<text x="{x0 + w + 10:.1f}" y="{y + 4:.1f}" class="dim">{top}</text>')
    svg.append(f'<text x="{x0 + w / 2:.1f}" y="{y0 + h + 30:.1f}" class="dim" text-anchor="middle">{W} mm</text>')
    svg.append(f'<text x="{x0 - 12:.1f}" y="{y0 + h / 2:.1f}" class="dim" text-anchor="middle" '
               f'transform="rotate(-90 {x0 - 12:.1f} {y0 + h / 2:.1f})">{H} mm</text>')
    svg.append("</svg>")
    return "".join(svg)


def sheet_view(layout, scale):
    L, Wd = SHEET
    svg = [f'<svg viewBox="0 0 {L * scale + 2} {Wd * scale + 2}" class="draw sheet" role="img" aria-label="Sheet layout">',
           f'<rect x="1" y="1" width="{L * scale}" height="{Wd * scale}" class="stock"/>']
    for name, x, y, a, b in layout:
        svg.append(f'<rect x="{1 + x * scale:.1f}" y="{1 + y * scale:.1f}" width="{a * scale:.1f}" '
                   f'height="{b * scale:.1f}" class="piece"/>')
        if a * scale > 60 and b * scale > 24:
            svg.append(f'<text x="{1 + (x + a / 2) * scale:.1f}" y="{1 + (y + b / 2) * scale:.1f}" '
                       f'class="lbl" text-anchor="middle" dominant-baseline="middle">'
                       f'{html.escape(name)} {a}×{b}</text>')
    svg.append("</svg>")
    return "".join(svg)


CSS = """
:root{--bg:#f7f5f0;--fg:#1d1c1a;--muted:#6b6760;--wood:#d9b98a;--wood-edge:#8a6a3d;--back:#efe6d6;
--line:#d8d2c6;--ok:#2f7d4f;--warn:#a86b00;--fail:#b3261e;--card:#fff}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#171614;--fg:#ece8e1;--muted:#a39d93;
--wood:#a9844f;--wood-edge:#e0c08f;--back:#2a2622;--line:#3a3530;--card:#201e1b}}
:root[data-theme="dark"]{--bg:#171614;--fg:#ece8e1;--muted:#a39d93;--wood:#a9844f;--wood-edge:#e0c08f;
--back:#2a2622;--line:#3a3530;--card:#201e1b}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);
font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
main{max-width:860px;margin:0 auto;padding:24px 16px 48px}
h1{font-size:22px;margin:0 0 4px}h2{font-size:16px;margin:28px 0 10px}.sub{color:var(--muted);margin:0}
.grid{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.2fr);gap:20px;align-items:start}
@media (max-width:640px){.grid{grid-template-columns:1fr}}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px}
.draw{width:100%;height:auto;display:block}.draw .board{fill:var(--wood);stroke:var(--wood-edge);stroke-width:1}
.draw .back{fill:var(--back);stroke:var(--line)}.draw .dim{font-size:12px;fill:var(--muted)}
.sheet .stock{fill:none;stroke:var(--muted);stroke-dasharray:4 3}.sheet .piece{fill:var(--wood);stroke:var(--wood-edge)}
.sheet .lbl{font-size:11px;fill:var(--fg)}
ul.checks{list-style:none;padding:0;margin:0}ul.checks li{padding:6px 0;border-bottom:1px solid var(--line)}
ul.checks li:last-child{border:0}.tag{font-weight:600;font-size:12px;margin-right:6px}
.ok .tag{color:var(--ok)}.warn .tag{color:var(--warn)}.fail .tag{color:var(--fail)}
table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}
td,th{text-align:left;padding:6px 4px;border-bottom:1px solid var(--line)}th{color:var(--muted);font-weight:500}
"""


def page(r):
    s = r.spec
    mat = MATERIALS[s["material"]]["name"]
    checks = "".join(f'<li class="{l}"><span class="tag">{l.upper()}</span>{html.escape(m)}</li>'
                     for l, m in r.checks)
    head = (f'<h1>Cabinet {s["width"]} × {s["height"]} × {s["depth"]} mm</h1>'
            f'<p class="sub">{s["shelves"]} shelves · {mat} {s["thickness"]} mm · '
            f'{s["load_kg_per_shelf"]:g} kg per shelf</p>')
    if not r.ok:
        body = f'{head}<h2>Checks</h2><div class="card"><ul class="checks">{checks}</ul></div>' \
               f'<p>Design rejected: fix the FAIL items first.</p>'
    else:
        scale = min(260 / s["width"], 420 / s["height"])
        rows = "".join(f'<tr><td>{p["qty"]}</td><td>{p["length"]} × {p["width"]}</td>'
                       f'<td>{p["thickness"]}</td><td>{html.escape(p["name"])}</td></tr>' for p in r.parts)
        hw = "".join(f'<tr><td>{n}</td><td colspan="3">{html.escape(k)}</td></tr>'
                     for k, n in r.hardware.items() if n)
        sheets = ""
        for sh in r.sheets:
            for i, lay in enumerate(sh["layout"], 1):
                sheets += (f'<p class="sub" style="margin-top:14px">Sheet {i}: {SHEET[0]} × {SHEET[1]} mm, {sh["thickness"]} mm</p>'
                           f'<div class="card">{sheet_view(lay, 0.3)}</div>')
        body = (f'{head}<div class="grid" style="margin-top:20px">'
                f'<div class="card">{front_view(r, scale)}</div>'
                f'<div><div class="card"><ul class="checks">{checks}</ul></div>'
                f'<h2>Cut list</h2><div class="card"><table><tr><th>Qty</th><th>Size (mm)</th>'
                f'<th>Thick</th><th>Part</th></tr>{rows}</table></div>'
                f'<h2>Hardware</h2><div class="card"><table>{hw}</table></div></div></div>'
                f'<h2>How to cut the sheets</h2>{sheets}')
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>Cabinet Plan</title><style>{CSS}</style></head><body><main>{body}</main></body></html>')


if __name__ == "__main__":
    r = design(Spec(**json.load(open(sys.argv[1]))))
    open(sys.argv[2], "w").write(page(r))
    print("wrote", sys.argv[2], "ok" if r.ok else "(rejected design)")
