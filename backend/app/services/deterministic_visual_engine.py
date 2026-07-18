"""Deterministic Visual Engine — crisp topic-specific explanatory SVG figures.

Used when reference images can't fill every slot (referential mode) or as the
renderer behind regenerated mode when no provider image model is configured.
Every figure is drawn from the planned labels/data, so it is topic-linked and
explanatory — never a random stock image.
"""
from __future__ import annotations

import html
import math

W, H = 960, 560
INK = "#2B3350"
SOFT = "#8A93B2"
GRID = "#E3E7F2"
ACCENT = "#4F6BF0"
ACCENT2 = "#E8734A"
ACCENT3 = "#2FA98C"
BG = "#FBFCFF"
FONT = "Segoe UI, Inter, Arial, sans-serif"


def _esc(t: str) -> str:
    return html.escape(str(t))


def _wrap(text: str, width: int) -> list[str]:
    words, lines, cur = str(text).split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 <= width:
            cur = f"{cur} {w}".strip()
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines[:3]


def _svg(body: str, title: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
        f'font-family="{FONT}">'
        f'<rect width="{W}" height="{H}" rx="18" fill="{BG}" '
        f'stroke="{GRID}"/>'
        f'<text x="{W/2}" y="44" text-anchor="middle" font-size="24" '
        f'font-weight="700" fill="{INK}">{_esc(title[:80])}</text>'
        f'{body}'
        f'<text x="{W-20}" y="{H-16}" text-anchor="end" font-size="12" '
        f'fill="{SOFT}">SEARCH AI · explanatory visual</text></svg>'
    )


def _axes(x0=90, y0=480, x1=900, y1=90, xl="", yl="") -> str:
    out = [f'<line x1="{x0}" y1="{y0}" x2="{x1}" y2="{y0}" stroke="{INK}" stroke-width="2"/>',
           f'<line x1="{x0}" y1="{y0}" x2="{x0}" y2="{y1}" stroke="{INK}" stroke-width="2"/>']
    for i in range(1, 6):
        gy = y0 - (y0 - y1) * i / 6
        out.append(f'<line x1="{x0}" y1="{gy}" x2="{x1}" y2="{gy}" '
                   f'stroke="{GRID}" stroke-width="1"/>')
    if xl:
        out.append(f'<text x="{(x0+x1)/2}" y="{y0+38}" text-anchor="middle" '
                   f'font-size="16" fill="{SOFT}">{_esc(xl[:60])}</text>')
    if yl:
        out.append(f'<text x="30" y="{(y0+y1)/2}" text-anchor="middle" '
                   f'font-size="16" fill="{SOFT}" '
                   f'transform="rotate(-90 30 {(y0+y1)/2})">{_esc(yl[:60])}</text>')
    return "".join(out)


def _poly(points: list[tuple[float, float]], color: str, dash: str = "") -> str:
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<polyline points="{pts}" fill="none" stroke="{color}" '
            f'stroke-width="3.5" stroke-linecap="round"{d}/>')


def _legend(items: list[tuple[str, str]], x=640, y=110) -> str:
    out = []
    for i, (label, color) in enumerate(items):
        yy = y + i * 28
        out.append(f'<rect x="{x}" y="{yy-11}" width="26" height="6" rx="3" fill="{color}"/>')
        out.append(f'<text x="{x+34}" y="{yy}" font-size="15" fill="{INK}">{_esc(label[:34])}</text>')
    return "".join(out)


# --------------------------------------------------------------- archetypes
def loss_curves(title: str, data: dict) -> str:
    x0, y0, x1, y1 = 90, 480, 900, 90
    train, val = [], []
    for i in range(61):
        t = i / 60
        x = x0 + (x1 - x0) * t
        tr = 0.9 * math.exp(-3.2 * t) + 0.05
        vl = 0.9 * math.exp(-2.6 * t) + 0.08 + 0.55 * max(0.0, t - 0.45) ** 1.6
        train.append((x, y0 - (y0 - y1) * (1 - tr)))
        val.append((x, y0 - (y0 - y1) * (1 - vl)))
    sweet_x = x0 + (x1 - x0) * 0.45
    body = _axes(xl=data.get("x_label", "Training epochs"),
                 yl=data.get("y_label", "Loss"))
    body += _poly(train, ACCENT) + _poly(val, ACCENT2)
    body += (f'<line x1="{sweet_x}" y1="{y1}" x2="{sweet_x}" y2="{y0}" '
             f'stroke="{ACCENT3}" stroke-width="2" stroke-dasharray="6 5"/>')
    body += (f'<text x="{sweet_x}" y="{y1-8}" text-anchor="middle" font-size="14" '
             f'fill="{ACCENT3}">early-stopping point</text>')
    body += (f'<text x="{x1-160}" y="{y1+70}" font-size="14" fill="{ACCENT2}">'
             f'validation diverges → overfitting</text>')
    body += _legend([("Training loss", ACCENT), ("Validation loss", ACCENT2)],
                    x=140, y=115)
    return _svg(body, title)


def error_complexity(title: str, data: dict) -> str:
    x0, y0, x1, y1 = 90, 480, 900, 90
    bias, var, total = [], [], []
    for i in range(61):
        t = i / 60
        x = x0 + (x1 - x0) * t
        b = 0.85 * math.exp(-2.8 * t) + 0.04
        v = 0.05 + 0.8 * t ** 2.2
        s = min(b + v, 1.15)
        bias.append((x, y0 - (y0 - y1) * (1 - b)))
        var.append((x, y0 - (y0 - y1) * (1 - v)))
        total.append((x, y0 - (y0 - y1) * (1 - s / 1.15)))
    body = _axes(xl="Model complexity", yl="Expected error")
    body += _poly(bias, ACCENT, dash="7 5") + _poly(var, ACCENT2, dash="7 5")
    body += _poly(total, INK)
    body += _legend([("Bias²", ACCENT), ("Variance", ACCENT2),
                     ("Total error", INK)], x=620, y=115)
    mid = 90 + (900 - 90) * 0.42
    body += (f'<line x1="{mid}" y1="{y1}" x2="{mid}" y2="{y0}" stroke="{ACCENT3}" '
             f'stroke-width="2" stroke-dasharray="6 5"/>'
             f'<text x="{mid}" y="{y1-8}" text-anchor="middle" font-size="14" '
             f'fill="{ACCENT3}">optimal complexity</text>'
             f'<text x="{mid-140}" y="{y0-20}" font-size="14" fill="{SOFT}">underfitting</text>'
             f'<text x="{mid+60}" y="{y0-20}" font-size="14" fill="{SOFT}">overfitting</text>')
    return _svg(body, title)


def distribution(title: str, data: dict) -> str:
    x0, y0, x1, y1 = 90, 480, 900, 90
    pts_in = data.get("points") or []
    body = _axes(xl=data.get("x_label", "x"),
                 yl="F(x)" if data.get("kind") == "cdf" else "Probability / density")
    if pts_in and all(isinstance(p, (list, tuple)) and len(p) == 2 for p in pts_in):
        xs = [float(p[0]) for p in pts_in]
        ys = [float(p[1]) for p in pts_in]
        xmin, xmax = min(xs), max(xs) or 1
        ymax = max(ys) or 1
        pts = [(x0 + (x1 - x0) * (x - xmin) / max(xmax - xmin, 1e-9),
                y0 - (y0 - y1) * y / ymax) for x, y in zip(xs, ys)]
        body += _poly(pts, ACCENT)
    elif data.get("kind") == "cdf":
        pts = []
        for i in range(61):
            t = i / 60
            y = 1 / (1 + math.exp(-8 * (t - 0.5)))
            pts.append((x0 + (x1 - x0) * t, y0 - (y0 - y1) * y))
        body += _poly(pts, ACCENT)
    elif data.get("kind") == "pmf":
        for i in range(9):
            t = (i + 0.5) / 9
            p = math.exp(-((t - 0.45) ** 2) / 0.045)
            bx = x0 + (x1 - x0) * t
            bh = (y0 - y1) * p * 0.9
            body += (f'<rect x="{bx-24}" y="{y0-bh}" width="48" height="{bh}" '
                     f'rx="6" fill="{ACCENT}" opacity="0.85"/>')
    else:  # pdf bell
        pts = []
        for i in range(61):
            t = i / 60
            y = math.exp(-((t - 0.5) ** 2) / 0.03)
            pts.append((x0 + (x1 - x0) * t, y0 - (y0 - y1) * y * 0.9))
        body += _poly(pts, ACCENT)
        mean_x = x0 + (x1 - x0) * 0.5
        body += (f'<line x1="{mean_x}" y1="{y0}" x2="{mean_x}" y2="{y1+20}" '
                 f'stroke="{ACCENT2}" stroke-width="2" stroke-dasharray="6 5"/>'
                 f'<text x="{mean_x+8}" y="{y1+40}" font-size="14" '
                 f'fill="{ACCENT2}">mean</text>')
    return _svg(body, title)


def timeline(title: str, data: dict) -> str:
    events = (data.get("events") or [])[:7]
    if not events:
        events = [{"label": "Origin", "year_or_date": ""},
                  {"label": "Development", "year_or_date": ""},
                  {"label": "Present", "year_or_date": ""}]
    y = 300
    x0, x1 = 90, 880
    body = (f'<line x1="{x0}" y1="{y}" x2="{x1}" y2="{y}" stroke="{INK}" '
            f'stroke-width="3"/>')
    n = len(events)
    for i, ev in enumerate(events):
        x = x0 + (x1 - x0) * (i / max(n - 1, 1))
        up = i % 2 == 0
        ty = y - 60 if up else y + 78
        body += (f'<circle cx="{x}" cy="{y}" r="9" fill="{ACCENT}"/>'
                 f'<line x1="{x}" y1="{y}" x2="{x}" y2="{y + (-38 if up else 38)}" '
                 f'stroke="{SOFT}" stroke-width="1.5"/>')
        date = _esc(ev.get("year_or_date", ""))
        if date:
            body += (f'<text x="{x}" y="{y + (-44 if up else 56)}" '
                     f'text-anchor="middle" font-size="15" font-weight="700" '
                     f'fill="{ACCENT2}">{date}</text>')
        for j, line in enumerate(_wrap(ev.get("label", ""), 20)):
            body += (f'<text x="{x}" y="{ty + j*18}" text-anchor="middle" '
                     f'font-size="14" fill="{INK}">{_esc(line)}</text>')
    return _svg(body, title)


def flowchart(title: str, data: dict) -> str:
    steps = (data.get("steps") or ["Input", "Process", "Output"])[:7]
    n = len(steps)
    bw, bh = min(200, int(760 / n) - 14), 92
    total = n * bw + (n - 1) * 46
    x = (W - total) / 2
    y = 250
    body = ""
    body += (f'<defs><marker id="ar" markerWidth="10" markerHeight="8" '
             f'refX="9" refY="4" orient="auto"><path d="M0,0 L10,4 L0,8 z" '
             f'fill="{SOFT}"/></marker></defs>')
    for i, step in enumerate(steps):
        bx = x + i * (bw + 46)
        body += (f'<rect x="{bx}" y="{y}" width="{bw}" height="{bh}" rx="14" '
                 f'fill="#EEF2FF" stroke="{ACCENT}" stroke-width="2"/>')
        lines = _wrap(step, max(14, bw // 9))
        ly = y + bh / 2 - (len(lines) - 1) * 10 + 5
        for j, line in enumerate(lines):
            body += (f'<text x="{bx+bw/2}" y="{ly + j*20}" text-anchor="middle" '
                     f'font-size="14" font-weight="600" fill="{INK}">{_esc(line)}</text>')
        if i < n - 1:
            body += (f'<line x1="{bx+bw}" y1="{y+bh/2}" x2="{bx+bw+40}" '
                     f'y2="{y+bh/2}" stroke="{SOFT}" stroke-width="2.5" '
                     f'marker-end="url(#ar)"/>')
    br = data.get("branch") or {}
    if br and isinstance(br.get("from"), int) and 0 <= br["from"] < n:
        bx = x + br["from"] * (bw + 46) + bw / 2
        body += (f'<line x1="{bx}" y1="{y+bh}" x2="{bx}" y2="{y+bh+70}" '
                 f'stroke="{ACCENT2}" stroke-width="2" marker-end="url(#ar)"/>'
                 f'<rect x="{bx-100}" y="{y+bh+70}" width="200" height="56" rx="12" '
                 f'fill="#FFF1EA" stroke="{ACCENT2}" stroke-width="2"/>')
        for j, line in enumerate(_wrap(br.get("to_label", br.get("label", "")), 24)):
            body += (f'<text x="{bx}" y="{y+bh+94+j*18}" text-anchor="middle" '
                     f'font-size="13" fill="{INK}">{_esc(line)}</text>')
    return _svg(body, title)


def architecture(title: str, data: dict) -> str:
    blocks = (data.get("blocks") or ["Client", "Service", "Store"])[:6]
    edges = data.get("edges") or [[i, i + 1] for i in range(len(blocks) - 1)]
    n = len(blocks)
    cols = min(3, n)
    rows = math.ceil(n / cols)
    bw, bh = 230, 96
    centers = []
    for i in range(n):
        r, c = divmod(i, cols)
        row_count = min(cols, n - r * cols)
        row_w = row_count * bw + (row_count - 1) * 90
        bx = (W - row_w) / 2 + c * (bw + 90)
        by = 120 + r * (bh + 110)
        centers.append((bx + bw / 2, by + bh / 2))
    body = (f'<defs><marker id="ar2" markerWidth="10" markerHeight="8" '
            f'refX="9" refY="4" orient="auto"><path d="M0,0 L10,4 L0,8 z" '
            f'fill="{SOFT}"/></marker></defs>')
    for a, b in edges[:10]:
        if not (isinstance(a, int) and isinstance(b, int)):
            continue
        if 0 <= a < n and 0 <= b < n:
            (x1c, y1c), (x2c, y2c) = centers[a], centers[b]
            body += (f'<line x1="{x1c}" y1="{y1c}" x2="{x2c}" y2="{y2c}" '
                     f'stroke="{SOFT}" stroke-width="2.5" marker-end="url(#ar2)"/>')
    for i, name in enumerate(blocks):
        cx, cy = centers[i]
        bx, by = cx - bw / 2, cy - bh / 2
        fill = ["#EEF2FF", "#EAF7F2", "#FFF4EC"][i % 3]
        stroke = [ACCENT, ACCENT3, ACCENT2][i % 3]
        body += (f'<rect x="{bx}" y="{by}" width="{bw}" height="{bh}" rx="16" '
                 f'fill="{fill}" stroke="{stroke}" stroke-width="2"/>')
        lines = _wrap(name, 24)
        ly = cy - (len(lines) - 1) * 10 + 5
        for j, line in enumerate(lines):
            body += (f'<text x="{cx}" y="{ly + j*20}" text-anchor="middle" '
                     f'font-size="15" font-weight="600" fill="{INK}">{_esc(line)}</text>')
    return _svg(body, title)


def comparison_bars(title: str, data: dict) -> str:
    labels = (data.get("labels") or ["A", "B", "C"])[:7]
    values = data.get("values") or []
    if len(values) != len(labels):
        values = [round(90 - i * 12.5, 1) for i in range(len(labels))]
    x0, y0, y1 = 90, 470, 100
    vmax = max(values) or 1
    slot = (900 - x0) / len(labels)
    body = _axes(y0=y0, yl=data.get("y_label", "Value"))
    colors = [ACCENT, ACCENT3, ACCENT2, "#9B6BF0", "#E0B23C", "#4FA6D9", "#D96B8F"]
    for i, (lab, val) in enumerate(zip(labels, values)):
        bh = (y0 - y1) * float(val) / vmax
        bx = x0 + slot * i + slot * 0.18
        bw = slot * 0.64
        body += (f'<rect x="{bx}" y="{y0-bh}" width="{bw}" height="{bh}" rx="8" '
                 f'fill="{colors[i % len(colors)]}" opacity="0.9"/>'
                 f'<text x="{bx+bw/2}" y="{y0-bh-10}" text-anchor="middle" '
                 f'font-size="14" font-weight="700" fill="{INK}">{_esc(val)}</text>')
        for j, line in enumerate(_wrap(lab, 16)):
            body += (f'<text x="{bx+bw/2}" y="{y0+22+j*16}" text-anchor="middle" '
                     f'font-size="13" fill="{INK}">{_esc(line)}</text>')
    return _svg(body, title)


def cycle(title: str, data: dict) -> str:
    phases = (data.get("phases") or ["Phase 1", "Phase 2", "Phase 3", "Phase 4"])[:6]
    cx, cy, r = W / 2, 310, 165
    n = len(phases)
    body = (f'<defs><marker id="ar3" markerWidth="9" markerHeight="7" refX="8" '
            f'refY="3.5" orient="auto"><path d="M0,0 L9,3.5 L0,7 z" '
            f'fill="{SOFT}"/></marker></defs>'
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{GRID}" '
            f'stroke-width="2" stroke-dasharray="4 6"/>')
    for i, phase in enumerate(phases):
        a0 = -math.pi / 2 + 2 * math.pi * i / n
        a1 = -math.pi / 2 + 2 * math.pi * (i + 0.72) / n
        x1c, y1c = cx + r * math.cos(a0), cy + r * math.sin(a0)
        x2c, y2c = cx + r * math.cos(a1), cy + r * math.sin(a1)
        body += (f'<path d="M {x1c:.1f} {y1c:.1f} A {r} {r} 0 0 1 '
                 f'{x2c:.1f} {y2c:.1f}" fill="none" stroke="{ACCENT}" '
                 f'stroke-width="3" marker-end="url(#ar3)"/>')
        lx = cx + (r + 74) * math.cos(a0)
        ly = cy + (r + 74) * math.sin(a0)
        body += (f'<circle cx="{x1c:.1f}" cy="{y1c:.1f}" r="8" fill="{ACCENT2}"/>')
        for j, line in enumerate(_wrap(phase, 18)):
            body += (f'<text x="{lx:.1f}" y="{ly + j*17:.1f}" text-anchor="middle" '
                     f'font-size="14" font-weight="600" fill="{INK}">{_esc(line)}</text>')
    return _svg(body, title)


def confusion_matrix(title: str, data: dict) -> str:
    labels = data.get("labels") or {}
    tp = labels.get("tp", "True Positive")
    fp = labels.get("fp", "False Positive")
    fn = labels.get("fn", "False Negative")
    tn = labels.get("tn", "True Negative")
    axis = data.get("axis") or ["Predicted", "Actual"]
    cw, ch = 280, 150
    x0, y0 = (W - 2 * cw) / 2 + 40, 140
    cells = [(tp, "#EAF7F2", ACCENT3, 0, 0), (fp, "#FFF1EA", ACCENT2, 1, 0),
             (fn, "#FFF1EA", ACCENT2, 0, 1), (tn, "#EAF7F2", ACCENT3, 1, 1)]
    body = ""
    for label, fill, stroke, c, r in cells:
        bx, by = x0 + c * cw, y0 + r * ch
        body += (f'<rect x="{bx}" y="{by}" width="{cw-10}" height="{ch-10}" '
                 f'rx="14" fill="{fill}" stroke="{stroke}" stroke-width="2"/>')
        for j, line in enumerate(_wrap(label, 26)):
            body += (f'<text x="{bx+(cw-10)/2}" y="{by+ch/2-8+j*19}" '
                     f'text-anchor="middle" font-size="15" font-weight="600" '
                     f'fill="{INK}">{_esc(line)}</text>')
    body += (f'<text x="{x0+cw-5}" y="{y0-40}" text-anchor="middle" font-size="17" '
             f'font-weight="700" fill="{SOFT}">{_esc(axis[0])} →</text>'
             f'<text x="{x0-46}" y="{y0+ch-5}" text-anchor="middle" font-size="17" '
             f'font-weight="700" fill="{SOFT}" transform="rotate(-90 {x0-46} '
             f'{y0+ch-5})">{_esc(axis[1] if len(axis)>1 else "Actual")} →</text>'
             f'<text x="{x0+(cw-10)/2}" y="{y0-14}" text-anchor="middle" '
             f'font-size="14" fill="{SOFT}">Positive</text>'
             f'<text x="{x0+cw+(cw-10)/2}" y="{y0-14}" text-anchor="middle" '
             f'font-size="14" fill="{SOFT}">Negative</text>')
    return _svg(body, title)


def time_series(title: str, data: dict) -> str:
    series = data.get("series") or []
    x0, y0, x1, y1 = 90, 480, 900, 90
    body = _axes(xl=data.get("x_label", "Time"),
                 yl=data.get("y_label", "Value"))
    colors = [ACCENT, ACCENT2, ACCENT3, "#9B6BF0"]
    legend = []
    valid = []
    for s in series[:4]:
        pts = [(float(p[0]), float(p[1])) for p in (s.get("points") or [])
               if isinstance(p, (list, tuple)) and len(p) == 2]
        if len(pts) >= 2:
            valid.append((s.get("name", "series"), pts))
    if not valid:
        pts = [(i, 40 + 22 * math.sin(i / 2.2) + i * 3.5) for i in range(20)]
        valid = [("indicative trend", pts)]
    all_x = [x for _, pts in valid for x, _ in pts]
    all_y = [y for _, pts in valid for _, y in pts]
    xmin, xmax = min(all_x), max(all_x)
    ymin, ymax = min(all_y), max(all_y)
    for i, (name, pts) in enumerate(valid):
        scaled = [(x0 + (x1 - x0) * (x - xmin) / max(xmax - xmin, 1e-9),
                   y0 - (y0 - y1) * (y - ymin) / max(ymax - ymin, 1e-9))
                  for x, y in pts]
        body += _poly(scaled, colors[i % 4])
        legend.append((name, colors[i % 4]))
    body += _legend(legend, x=640, y=112)
    return _svg(body, title)


RENDERERS = {
    "loss_curves": loss_curves,
    "error_complexity": error_complexity,
    "distribution": distribution,
    "timeline": timeline,
    "flowchart": flowchart,
    "architecture": architecture,
    "comparison_bars": comparison_bars,
    "cycle": cycle,
    "confusion_matrix": confusion_matrix,
    "time_series": time_series,
}


def render(archetype: str, topic: str, title: str, data: dict) -> str:
    fn = RENDERERS.get(archetype, flowchart)
    try:
        return fn(title or topic, data or {})
    except Exception:
        return flowchart(title or topic, {"steps": ["Concept", "Mechanism",
                                                    "Outcome"]})
