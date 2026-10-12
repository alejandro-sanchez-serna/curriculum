#!/usr/bin/env python3
"""Genera el mundo isométrico (SVG) y lo inyecta en index.html.

Uso:  python3 tools/build_world.py
Reescribe el bloque entre <!-- world:start --> y <!-- world:end --> de index.html
y el bloque de colores entre /* world-colors:start */ y /* world-colors:end */
de assets/site.css.
"""
import math, re, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

T = 40                      # lado de una baldosa
CX = T * math.cos(math.radians(30))
CY = T * 0.5
ZS = 32                     # altura de una unidad vertical

def P(x, y, z=0.0):
    return ((x - y) * CX, (x + y) * CY - z * ZS)

def pts(points):
    return " ".join(f"{px:.1f},{py:.1f}" for px, py in (P(*p) for p in points))

# ---------------------------------------------------------------- materiales
# (top, left, right) en claro; el oscuro se calcula mezclando hacia la noche
MATS = {
    "paper": ("#FBFAF6", "#E7E3D9", "#D3CEC2"),
    "stone": ("#ECE6DA", "#D3CAB8", "#BCB19C"),
    "terra": ("#DE916B", "#C8673E", "#A65130"),
    "ink":   ("#46658C", "#1F3A5F", "#162B47"),
    "sage":  ("#B6CBB1", "#8FA88A", "#728B6E"),
    "grass": ("#C3D5BC", "#A7BE9F", "#8CA484"),
    "earth": ("#B0927A", "#9B7B62", "#7F6450"),
    "road":  ("#E4DED2", "#CFC8B8", "#BAB2A0"),
    "wood":  ("#D4AE88", "#B48C64", "#94704E"),
    "slate": ("#5B6472", "#454D59", "#363C46"),
}
SINGLE = {
    "glass": ("#A9BED3", "#F2C46D"),   # claro / oscuro (ventanas encendidas)
    "water": ("#A5C6D3", "#284660"),
    "board": ("#355446", "#2B4538"),
    "chalk": ("#EEF1EA", "#DCE3D8"),
    "skin1": ("#E9B998", "#C79A7C"),
    "skin2": ("#B9805A", "#99694A"),
    "skin3": ("#7A4E33", "#644029"),
    "shade": ("#1F3A5F", "#000000"),
}
NIGHT = "#141B26"

def mix(a, b, t):
    a = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02X}" for x, y in zip(a, b))

def css_vars():
    light, dark = [], []
    for m, shades in MATS.items():
        for s, col in zip("tlr", shades):
            light.append(f"--w-{m}-{s}:{col}")
            dark.append(f"--w-{m}-{s}:{mix(col, NIGHT, 0.58)}")
    for m, (l, d) in SINGLE.items():
        light.append(f"--w-{m}:{l}")
        dark.append(f"--w-{m}:{d}")
    rules = []
    for m in MATS:
        for s in "tlr":
            rules.append(f".{m}-{s}{{fill:var(--w-{m}-{s})}}")
    for m in SINGLE:
        rules.append(f".{m}{{fill:var(--w-{m})}}")
    return light, dark, rules

# ---------------------------------------------------------------- primitivas
class Scene:
    def __init__(self, sid, ox, oy, label):
        self.sid, self.ox, self.oy, self.label = sid, ox, oy, label
        self.items = []          # (depth, svg)
        self.under = []          # isla y carretera (siempre detrás)

    def add(self, depth, svg):
        self.items.append((depth, svg))

    # coordenadas locales -> mundo
    def w(self, x, y):
        return x + self.ox, y + self.oy

    def box(self, x, y, z, w, d, h, mat, windows=None):
        X, Y = self.w(x, y)
        top = [(X, Y, z + h), (X + w, Y, z + h), (X + w, Y + d, z + h), (X, Y + d, z + h)]
        left = [(X, Y + d, z), (X + w, Y + d, z), (X + w, Y + d, z + h), (X, Y + d, z + h)]
        right = [(X + w, Y, z), (X + w, Y + d, z), (X + w, Y + d, z + h), (X + w, Y, z + h)]
        svg = (f'<polygon class="{mat}-l" points="{pts(left)}"/>'
               f'<polygon class="{mat}-r" points="{pts(right)}"/>'
               f'<polygon class="{mat}-t" points="{pts(top)}"/>')
        if windows:
            svg += windows(X, Y, z, w, d, h)
        self.add(X + w / 2 + Y + d / 2 + z * 0.01, svg)

    def flat(self, poly, cls, depth=None, under=False):
        world = [(*self.w(x, y), z) for x, y, z in poly]
        svg = f'<polygon class="{cls}" points="{pts(world)}"/>'
        if under:
            self.under.append(svg)
        else:
            cx = sum(p[0] + p[1] for p in world) / len(world)
            self.add(depth if depth is not None else cx, svg)

    def raw(self, depth, svg):
        self.add(depth, svg)

    def pt(self, x, y, z=0):
        X, Y = self.w(x, y)
        return P(X, Y, z)

    def svg(self, i=0):
        body = "".join(self.under) + "".join(s for _, s in sorted(self.items, key=lambda i: i[0]))
        cx, cy = P(self.ox + 6, self.oy + 6, 1.6)
        return (f'<g class="scene" style="--i:{i}" id="scene-{self.sid}" data-cx="{cx:.1f}" data-cy="{cy:.1f}">'
                f'<title>{self.label}</title>{body}</g>')

# ventanas -------------------------------------------------------------------
def win_grid(cols, rows, mx=0.25, mz=0.35, gap=0.22, faces="lr", cls="glass"):
    def f(X, Y, z, w, d, h):
        out = []
        if "l" in faces:
            cw = (w - 2 * mx - gap * (cols - 1)) / cols
            rh = (h - 2 * mz - gap * (rows - 1)) / rows
            for c in range(cols):
                for r in range(rows):
                    u0 = X + mx + c * (cw + gap); v0 = z + mz + r * (rh + gap)
                    q = [(u0, Y + d, v0), (u0 + cw, Y + d, v0), (u0 + cw, Y + d, v0 + rh), (u0, Y + d, v0 + rh)]
                    out.append(f'<polygon class="{cls}" points="{pts(q)}"/>')
        if "r" in faces:
            cd = max(1, round(cols * d / max(w, 0.1)))
            cw = (d - 2 * mx - gap * (cd - 1)) / cd
            rh = (h - 2 * mz - gap * (rows - 1)) / rows
            for c in range(cd):
                for r in range(rows):
                    u0 = Y + mx + c * (cw + gap); v0 = z + mz + r * (rh + gap)
                    q = [(X + w, u0, v0), (X + w, u0 + cw, v0), (X + w, u0 + cw, v0 + rh), (X + w, u0, v0 + rh)]
                    out.append(f'<polygon class="{cls} dim" points="{pts(q)}"/>')
        return "".join(out)
    return f

def door_left(u, width=0.7, height=1.1, cls="ink-l"):
    def f(X, Y, z, w, d, h):
        q = [(X + u, Y + d, z), (X + u + width, Y + d, z), (X + u + width, Y + d, z + height), (X + u, Y + d, z + height)]
        return f'<polygon class="{cls}" points="{pts(q)}"/>'
    return f

def combo(*fs):
    return lambda *a: "".join(fn(*a) for fn in fs)

# objetos ---------------------------------------------------------------------
def tree(s, x, y, size=1.0, mat="sage"):
    bx, by = s.pt(x, y, 0)
    r = 15 * size
    trunk_h = 18 * size
    cy = by - trunk_h - r * 0.7
    svg = (f'<ellipse class="shadow" cx="{bx:.1f}" cy="{by:.1f}" rx="{r*0.9:.1f}" ry="{r*0.45:.1f}"/>'
           f'<rect class="wood-r" x="{bx-2.5*size:.1f}" y="{by-trunk_h:.1f}" width="{5*size:.1f}" height="{trunk_h:.1f}" rx="1.5"/>'
           f'<circle class="{mat}-r" cx="{bx+2*size:.1f}" cy="{cy+2*size:.1f}" r="{r:.1f}"/>'
           f'<circle class="{mat}-l" cx="{bx:.1f}" cy="{cy:.1f}" r="{r:.1f}"/>'
           f'<circle class="{mat}-t" cx="{bx-r*0.28:.1f}" cy="{cy-r*0.3:.1f}" r="{r*0.55:.1f}"/>')
    X, Y = s.w(x, y)
    s.add(X + Y, svg)

def person(s, x, y, body="terra-l", skin="skin1", z=0, scale=1.0):
    bx, by = s.pt(x, y, z)
    k = scale
    svg = (f'<ellipse class="shadow" cx="{bx:.1f}" cy="{by:.1f}" rx="{6*k:.1f}" ry="{2.6*k:.1f}"/>'
           f'<rect class="{body}" x="{bx-4*k:.1f}" y="{by-15*k:.1f}" width="{8*k:.1f}" height="{14*k:.1f}" rx="{3.5*k:.1f}"/>'
           f'<circle class="{skin}" cx="{bx:.1f}" cy="{by-19*k:.1f}" r="{4*k:.1f}"/>')
    X, Y = s.w(x, y)
    s.add(X + Y + 0.05, svg)

def lamp(s, x, y, h=2.2):
    bx, by = s.pt(x, y, 0)
    tx, ty = s.pt(x, y, h)
    svg = (f'<line class="post" x1="{bx:.1f}" y1="{by:.1f}" x2="{tx:.1f}" y2="{ty:.1f}"/>'
           f'<circle class="glass lamp" cx="{tx:.1f}" cy="{ty:.1f}" r="4.5"/>')
    X, Y = s.w(x, y)
    s.add(X + Y, svg)

def bench(s, x, y):
    s.box(x, y, 0.25, 1.2, 0.45, 0.12, "wood")
    s.box(x, y, 0.37, 1.2, 0.1, 0.4, "wood")

# ---------------------------------------------------------------- isla
def island(s, top="grass"):
    X, Y = s.ox, s.oy
    for z0, h, mat in ((-1.5, 1.05, "earth"), (-0.45, 0.45, top)):
        left = [(X, Y + 12, z0), (X + 12, Y + 12, z0), (X + 12, Y + 12, z0 + h), (X, Y + 12, z0 + h)]
        right = [(X + 12, Y, z0), (X + 12, Y + 12, z0), (X + 12, Y + 12, z0 + h), (X + 12, Y, z0 + h)]
        s.under.append(f'<polygon class="{mat}-l" points="{pts(left)}"/><polygon class="{mat}-r" points="{pts(right)}"/>')
    topq = [(X, Y, 0), (X + 12, Y, 0), (X + 12, Y + 12, 0), (X, Y + 12, 0)]
    s.under.append(f'<polygon class="{top}-t" points="{pts(topq)}"/>')
    road = [(X, Y + 5, 0), (X + 12, Y + 5, 0), (X + 12, Y + 7, 0), (X, Y + 7, 0)]
    s.under.append(f'<polygon class="road-t" points="{pts(road)}"/>')
    # marcas centrales
    for i in range(6):
        a = X + 0.6 + i * 2
        q = [(a, Y + 5.94, 0), (a + 0.9, Y + 5.94, 0), (a + 0.9, Y + 6.06, 0), (a, Y + 6.06, 0)]
        s.under.append(f'<polygon class="paper-t" points="{pts(q)}"/>')

# ---------------------------------------------------------------- escenas
ORIGINS = [(0, 0), (14, 8), (28, 0), (42, 8), (56, 0), (70, 8)]

def madrid():
    s = Scene("madrid", *ORIGINS[0], "Madrid")
    island(s, "grass")
    # edificios clásicos al fondo
    s.box(0.4, 0.5, 0, 2.2, 2.6, 3.2, "stone", win_grid(2, 3))
    s.box(2.8, 0.8, 0, 1.8, 2.4, 2.4, "terra", win_grid(2, 2))
    # edificio con cúpula (guiño al Metrópolis)
    s.box(4.8, 0.6, 0, 2.0, 2.4, 3.6, "paper", combo(win_grid(2, 3), door_left(0.65)))
    cx, cy = s.pt(5.8, 1.8, 3.6)
    s.raw(4.8 + 1 + 0.6 + 1.2 + 0.02 + 0.01 * 3.6 + 0.05,
          f'<rect class="paper-r" x="{cx-17:.1f}" y="{cy-10:.1f}" width="34" height="12"/>'
          f'<path class="slate-l" d="M{cx-17:.1f},{cy-10:.1f} a17,17 0 0 1 34,0 z"/>'
          f'<path class="slate-t" d="M{cx-11:.1f},{cy-16:.1f} a12,12 0 0 1 14,-7 a17,17 0 0 0 -14,7 z"/>'
          f'<line class="post" x1="{cx:.1f}" y1="{cy-27:.1f}" x2="{cx:.1f}" y2="{cy-38:.1f}"/>'
          f'<circle class="terra-l" cx="{cx:.1f}" cy="{cy-40:.1f}" r="3"/>')
    # Cuatro Torres
    for i, (x, h) in enumerate(((7.4, 6.6), (8.6, 7.8), (9.8, 7.2), (11.0, 8.4))):
        s.box(x, 0.6 + i * 0.25, 0, 0.85, 0.85, h, "ink" if i % 2 else "stone",
              win_grid(1, int(h * 1.6), mx=0.18, mz=0.3, gap=0.16))
    # cuarto de estudiante abierto, delante
    s.box(0.6, 8.0, 0, 4.4, 3.4, 0.12, "wood")
    s.box(0.6, 8.0, 0.12, 4.4, 0.18, 1.4, "paper")
    s.box(0.6, 8.18, 0.12, 0.18, 3.22, 1.4, "stone")
    s.box(2.0, 8.5, 0.12, 2.0, 0.9, 0.62, "wood")               # escritorio
    s.box(2.5, 8.6, 0.74, 0.9, 0.55, 0.05, "slate")             # portátil
    s.box(2.5, 8.6, 0.79, 0.9, 0.06, 0.5, "slate")
    s.box(3.55, 8.65, 0.74, 0.3, 0.4, 0.12, "terra")            # libros
    s.box(3.55, 8.65, 0.86, 0.3, 0.4, 0.1, "ink")
    s.box(2.6, 9.7, 0.12, 0.6, 0.6, 0.45, "ink")                # silla
    tree(s, 7.2, 9.0, 1.05)
    tree(s, 10.4, 10.2, 0.9, "terra")
    lamp(s, 6.0, 7.6)
    bench(s, 8.4, 8.0)
    return s

def plaza():
    s = Scene("plaza", *ORIGINS[1], "Sobre mí")
    island(s, "stone")
    # baldosas de plaza
    for i in range(0, 12, 2):
        for j in (0, 8, 10):
            if (i // 2 + j // 2) % 2 == 0:
                q = [(i, j, 0), (i + 2, j, 0), (i + 2, j + 2, 0), (i, j + 2, 0)]
                s.flat(q, "paper-t", under=True)
    # soportales al fondo
    s.box(0.3, 0.4, 0, 7.4, 2.4, 3.0, "terra", combo(win_grid(6, 1, mz=1.6, gap=0.35), win_grid(6, 1, mz=0.0, gap=0.35, faces="l", cls="terra-r arch")))
    s.box(8.2, 0.4, 0, 3.4, 2.4, 3.6, "stone", combo(win_grid(3, 2, mz=1.4), door_left(1.3, 0.8, 1.2)))
    # mostrador con toldo (atención al público)
    s.box(1.0, 8.6, 0, 3.0, 1.0, 0.9, "wood")
    s.box(1.0, 8.6, 0.9, 3.0, 1.0, 0.08, "paper")
    for i in range(4):
        s.box(1.0 + i * 0.75, 8.1, 1.9, 0.75, 1.2, 0.12, "terra" if i % 2 == 0 else "paper")
    s.box(1.0, 8.1, 0.9, 0.08, 0.08, 1.0, "slate")
    s.box(3.92, 8.1, 0.9, 0.08, 0.08, 1.0, "slate")
    person(s, 2.4, 8.25, "ink-l", "skin2")
    person(s, 2.0, 10.6, "sage-l", "skin1")
    person(s, 3.2, 10.4, "terra-r", "skin3")
    # fuente
    fx, fy = s.pt(8.2, 9.8, 0)
    s.raw(18 + 8.2 + 9.8 + 0.5,
          f'<ellipse class="stone-r" cx="{fx:.1f}" cy="{fy:.1f}" rx="44" ry="24"/>'
          f'<ellipse class="stone-t" cx="{fx:.1f}" cy="{fy-8:.1f}" rx="44" ry="24"/>'
          f'<ellipse class="water" cx="{fx:.1f}" cy="{fy-8:.1f}" rx="36" ry="19"/>'
          f'<rect class="stone-l" x="{fx-5:.1f}" y="{fy-34:.1f}" width="10" height="26"/>'
          f'<ellipse class="stone-t" cx="{fx:.1f}" cy="{fy-34:.1f}" rx="14" ry="7"/>'
          f'<path class="spray" d="M{fx:.1f},{fy-36:.1f} q-10,-16 -18,4 M{fx:.1f},{fy-36:.1f} q10,-16 18,4"/>')
    person(s, 10.6, 8.2, "slate-l", "skin2")
    tree(s, 11.2, 10.8, 0.85)
    lamp(s, 5.6, 7.7)
    return s

def campus():
    s = Scene("campus", *ORIGINS[2], "Formación")
    island(s, "grass")
    # facultad
    s.box(0.3, 0.4, 0, 5.4, 3.0, 2.4, "paper", combo(win_grid(5, 2), door_left(2.3, 0.8, 1.0)))
    for i in range(6):
        s.box(0.45 + i * 1.0, 3.35, 0, 0.18, 0.18, 2.4, "stone")
    s.box(0.3, 0.4, 2.4, 5.4, 3.3, 0.18, "ink")
    # biblioteca con lomos de libros
    def spines(X, Y, z, w, d, h):
        out = []
        cols = ["terra-l", "ink-l", "sage-l", "wood-l", "paper-r"]
        n = 14
        for i in range(n):
            u0 = Y + 0.2 + i * (d - 0.4) / n
            u1 = u0 + (d - 0.4) / n * 0.8
            hh = 0.9 + (i * 37 % 5) * 0.08
            q = [(X + w, u0, z + 0.3), (X + w, u1, z + 0.3), (X + w, u1, z + 0.3 + hh), (X + w, u0, z + 0.3 + hh)]
            out.append(f'<polygon class="{cols[i % 5]}" points="{pts(q)}"/>')
        return out and "".join(out)
    s.box(6.3, 0.5, 0, 2.6, 3.0, 3.0, "stone", combo(win_grid(2, 2, faces="l"), spines))
    # pantalla de bolsa
    def chart(X, Y, z, w, d, h):
        bg = [(X + 0.1, Y + d, z + 0.1), (X + w - 0.1, Y + d, z + 0.1), (X + w - 0.1, Y + d, z + h - 0.1), (X + 0.1, Y + d, z + h - 0.1)]
        vals = [0.2, 0.35, 0.3, 0.5, 0.45, 0.62, 0.58, 0.8]
        line = [(X + 0.25 + i * (w - 0.5) / (len(vals) - 1), Y + d, z + 0.2 + v * (h - 0.45)) for i, v in enumerate(vals)]
        return (f'<polygon class="slate-l" points="{pts(bg)}"/>'
                f'<polyline class="chartline" points="{pts(line)}"/>')
    s.box(9.4, 1.0, 1.4, 2.3, 0.25, 1.6, "slate", chart)
    s.box(10.4, 1.05, 0, 0.18, 0.18, 1.4, "slate")
    # libros gigantes delante
    s.box(1.0, 8.4, 0, 2.0, 1.4, 0.4, "ink")
    s.box(1.1, 8.5, 0.4, 1.8, 1.2, 0.35, "terra")
    s.box(1.2, 8.55, 0.75, 1.7, 1.1, 0.3, "sage")
    # balanza
    bx, by = s.pt(5.0, 9.2, 0)
    s.raw(14.2 + 28, f'<ellipse class="shadow" cx="{bx:.1f}" cy="{by:.1f}" rx="16" ry="6"/>'
          f'<rect class="wood-l" x="{bx-9:.1f}" y="{by-6:.1f}" width="18" height="6" rx="2"/>'
          f'<line class="post" x1="{bx:.1f}" y1="{by-6:.1f}" x2="{bx:.1f}" y2="{by-46:.1f}"/>'
          f'<line class="post" x1="{bx-22:.1f}" y1="{by-42:.1f}" x2="{bx+22:.1f}" y2="{by-42:.1f}"/>'
          f'<path class="thread" d="M{bx-22:.1f},{by-42:.1f} l-8,18 M{bx-22:.1f},{by-42:.1f} l8,18 M{bx+22:.1f},{by-42:.1f} l-8,18 M{bx+22:.1f},{by-42:.1f} l8,18"/>'
          f'<path class="terra-l" d="M{bx-32:.1f},{by-24:.1f} q10,8 20,0 z"/>'
          f'<path class="terra-l" d="M{bx+12:.1f},{by-24:.1f} q10,8 20,0 z"/>'
          f'<circle class="terra-t" cx="{bx:.1f}" cy="{by-47:.1f}" r="3"/>')
    person(s, 7.4, 8.6, "ink-l", "skin3")
    person(s, 8.1, 8.9, "terra-l", "skin1")
    tree(s, 10.0, 9.4, 1.1)
    tree(s, 11.2, 11.0, 0.8, "terra")
    lamp(s, 3.8, 7.7)
    return s

def aula():
    s = Scene("aula", *ORIGINS[3], "Experiencia")
    island(s, "grass")
    # instituto con tejado a dos aguas
    s.box(0.4, 0.4, 0, 6.6, 3.0, 2.6, "terra", combo(win_grid(6, 2), door_left(2.9, 0.8, 1.1, "paper-r")))
    X, Y = s.w(0.4, 0.4)
    ridge_z = 2.6 + 1.3
    roof_front = [(X, Y + 3.0, 2.6), (X + 6.6, Y + 3.0, 2.6), (X + 6.6, Y + 1.5, ridge_z), (X, Y + 1.5, ridge_z)]
    gable = [(X + 6.6, Y, 2.6), (X + 6.6, Y + 3.0, 2.6), (X + 6.6, Y + 1.5, ridge_z)]
    s.add(X + 3.3 + Y + 1.5 + 0.1, f'<polygon class="paper-r" points="{pts(gable)}"/><polygon class="slate-t" points="{pts(roof_front)}"/>')
    # reloj
    cx, cy = s.pt(3.7, 3.4, 2.15)
    s.add(X + 3.3 + Y + 1.5 + 0.12, f'<circle class="paper-t" cx="{cx:.1f}" cy="{cy:.1f}" r="9"/><path class="hand" d="M{cx:.1f},{cy:.1f} v-6 M{cx:.1f},{cy:.1f} h5"/>')
    # pista / patio
    s.box(7.6, 0.6, 0, 4.0, 3.2, 0.06, "sage")
    s.box(9.4, 0.8, 0.06, 0.12, 0.12, 1.6, "paper")
    s.box(9.4, 3.4, 0.06, 0.12, 0.12, 1.6, "paper")
    s.box(9.4, 0.8, 1.6, 0.12, 2.72, 0.1, "paper")
    # aula abierta con pizarra y grupos de estudio
    s.box(0.6, 8.0, 0, 6.2, 3.6, 0.12, "wood")
    def board(X, Y, z, w, d, h):
        q = [(X + 0.6, Y + d, z + 0.45), (X + w - 0.6, Y + d, z + 0.45), (X + w - 0.6, Y + d, z + h - 0.15), (X + 0.6, Y + d, z + h - 0.15)]
        a = [(X + 1.0 + i * 0.12, Y + d, z + 0.6 + 0.6 * math.sin(i / 3.2)) for i in range(18)]
        tri = [(X + 3.6, Y + d, z + 0.6), (X + 4.6, Y + d, z + 0.6), (X + 3.6, Y + d, z + 1.2), (X + 3.6, Y + d, z + 0.6)]
        return (f'<polygon class="board" points="{pts(q)}"/>'
                f'<polyline class="chalkline" points="{pts(a)}"/><polyline class="chalkline" points="{pts(tri)}"/>')
    s.box(0.6, 8.0, 0.12, 6.2, 0.18, 1.5, "paper", board)
    for gx in (1.4, 4.2):
        s.box(gx, 9.3, 0.12, 1.5, 1.0, 0.45, "wood")
        s.box(gx, 9.3, 0.57, 1.5, 1.0, 0.05, "paper")
        person(s, gx - 0.15, 9.8, "ink-l", "skin1", z=0.12, scale=0.85)
        person(s, gx + 0.7, 10.55, "sage-l", "skin2", z=0.12, scale=0.85)
        person(s, gx + 1.65, 9.9, "terra-l", "skin3", z=0.12, scale=0.85)
    person(s, 3.4, 8.55, "slate-l", "skin2", z=0.12)     # profesor
    tree(s, 9.0, 9.6, 1.1)
    tree(s, 10.8, 10.8, 0.85, "terra")
    lamp(s, 8.0, 7.7)
    return s

def gante():
    s = Scene("gante", *ORIGINS[4], "Idiomas")
    island(s, "stone")
    # canal delante
    water = [(0, 8.2, -0.25), (12, 8.2, -0.25), (12, 11.2, -0.25), (0, 11.2, -0.25)]
    s.flat(water, "water", under=True)
    for a, b in ((0, 8.0), (0, 11.2)):
        q = [(0, b, 0), (12, b, 0), (12, b + 0.2, 0), (0, b + 0.2, 0)]
        s.flat(q, "stone-t", under=True)
    for i in range(7):
        a = 0.6 + i * 1.65
        b = 8.9 + (i * 5 % 3) * 0.55
        q = [(a, b, -0.24), (a + 0.45, b, -0.24), (a + 0.45, b + 0.07, -0.24), (a, b + 0.07, -0.24)]
        s.flat(q, "ripple", under=True)
    # casas flamencas con frontón escalonado
    houses = [("terra", 2.6), ("paper", 3.2), ("ink", 2.9), ("sage", 3.4), ("stone", 2.7), ("terra", 3.1)]
    x = 0.3
    for i, (mat, h) in enumerate(houses):
        w = 1.75
        s.box(x, 0.6, 0, w, 2.6, h, mat, combo(win_grid(2, 2, mz=0.4, faces="l"), door_left(0.55, 0.6, 0.95, "slate-l")))
        inset, zz, ww = 0.0, h, w
        for step in range(3):
            inset += 0.22
            ww = w - 2 * inset
            s.box(x + inset, 2.85, zz, ww, 0.35, 0.32, mat)
            zz += 0.32
        x += w + 0.18
    # barco en el canal
    s.box(3.2, 9.3, -0.2, 2.2, 0.8, 0.35, "wood")
    s.box(3.8, 9.45, 0.15, 0.9, 0.5, 0.35, "paper")
    # bicicletas junto a la carretera
    for i in range(3):
        bx, by = s.pt(7.6 + i * 0.9, 4.6, 0)
        s.add(56 + 7.6 + i * 0.9 + 4.6, f'<g class="bike"><circle cx="{bx-7:.1f}" cy="{by-5:.1f}" r="5"/><circle cx="{bx+7:.1f}" cy="{by-5:.1f}" r="5"/>'
              f'<path d="M{bx-7:.1f},{by-5:.1f} l5,-8 h7 l2,8 M{bx-2:.1f},{by-13:.1f} l-1,-3 M{bx+5:.1f},{by-13:.1f} l1,-4"/></g>')
    # banderines de idiomas sobre la carretera (ES, EN, NL)
    a = s.pt(4.0, 4.6, 2.6)
    b = s.pt(4.0, 7.4, 2.6)
    p1, p2 = s.pt(4.0, 4.6, 0), s.pt(4.0, 7.4, 0)
    flags = ""
    for i, fid in enumerate(("es", "en", "nl")):
        t0 = 0.18 + i * 0.25
        t1 = t0 + 0.17
        sag = lambda t: 10 * math.sin(math.pi * t)
        q0 = (a[0] + (b[0] - a[0]) * t0, a[1] + (b[1] - a[1]) * t0 + sag(t0))
        q1 = (a[0] + (b[0] - a[0]) * t1, a[1] + (b[1] - a[1]) * t1 + sag(t1))
        tip = ((q0[0] + q1[0]) / 2, (q0[1] + q1[1]) / 2 + 26)
        flags += f'<polygon fill="url(#flag-{fid})" class="flag" points="{q0[0]:.1f},{q0[1]:.1f} {q1[0]:.1f},{q1[1]:.1f} {tip[0]:.1f},{tip[1]:.1f}"/>'
    mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2 + 10)
    s.add(56 + 4.0 + 7.4 + 1.0,
          f'<line class="post" x1="{p1[0]:.1f}" y1="{p1[1]:.1f}" x2="{a[0]:.1f}" y2="{a[1]:.1f}"/>'
          f'<line class="post" x1="{p2[0]:.1f}" y1="{p2[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}"/>'
          f'<path class="thread" d="M{a[0]:.1f},{a[1]:.1f} Q{mid[0]:.1f},{mid[1]+10:.1f} {b[0]:.1f},{b[1]:.1f}"/>{flags}')
    person(s, 9.8, 7.6, "ink-l", "skin1")
    tree(s, 11.3, 4.3, 0.8)
    lamp(s, 1.2, 7.6)
    return s

def correos():
    s = Scene("correos", *ORIGINS[5], "Contacto")
    island(s, "grass")
    # oficina de correos con puerta abierta
    def facade(X, Y, z, w, d, h):
        door = [(X + 2.0, Y + d, z), (X + 3.0, Y + d, z), (X + 3.0, Y + d, z + 1.4), (X + 2.0, Y + d, z + 1.4)]
        leaf = [(X + 3.0, Y + d, z), (X + 3.0, Y + d + 0.7, z), (X + 3.0, Y + d + 0.7, z + 1.4), (X + 3.0, Y + d, z + 1.4)]
        return (f'<polygon class="glass doorlight" points="{pts(door)}"/>'
                f'<polygon class="ink-r" points="{pts(leaf)}"/>')
    s.box(0.5, 0.5, 0, 5.2, 3.0, 2.8, "paper", combo(win_grid(4, 1, mz=1.65, gap=0.4), facade))
    s.box(0.5, 0.5, 2.8, 5.2, 3.0, 0.3, "ink")
    cx, cy = s.pt(1.3, 3.5, 2.25)
    s.add(0.5 + 2.6 + 0.5 + 1.5 + 0.12, f'<circle class="paper-t" cx="{cx:.1f}" cy="{cy:.1f}" r="8"/><path class="hand" d="M{cx:.1f},{cy:.1f} v-5 M{cx:.1f},{cy:.1f} h4"/>')
    s.box(6.4, 0.8, 0, 2.2, 2.4, 1.9, "terra", win_grid(2, 1, mz=0.6))
    s.box(9.0, 0.6, 0, 2.4, 2.6, 2.3, "stone", win_grid(2, 2, mz=0.5))
    # buzón grande
    s.box(2.6, 8.5, 0, 1.0, 0.8, 1.5, "terra")
    bx, by = s.pt(3.1, 8.9, 1.5)
    s.raw(70 + 8 + 3.1 + 8.9 + 0.2, f'<path class="terra-t" d="M{bx-24:.1f},{by:.1f} a24,13 0 0 1 48,0 a24,12 0 0 1 -48,0 z"/>')
    sx, sy = s.pt(2.95, 9.3, 1.15)
    s.raw(70 + 8 + 3.1 + 8.9 + 0.3, f'<rect class="slate-l" x="{sx-10:.1f}" y="{sy-2:.1f}" width="14" height="3" rx="1.5" transform="rotate(-30 {sx:.1f} {sy:.1f})"/>')
    # aviones de papel
    for i, (x, y, z) in enumerate(((5.6, 9.4, 2.2), (7.6, 8.4, 3.0), (9.6, 9.6, 2.5))):
        px, py = s.pt(x, y, z)
        s.raw(200 + i, f'<g class="plane" style="--i:{i}"><polygon class="paper-t" points="{px-12:.1f},{py:.1f} {px+12:.1f},{py-6:.1f} {px-2:.1f},{py+3:.1f}"/>'
              f'<polygon class="paper-r" points="{px-2:.1f},{py+3:.1f} {px+12:.1f},{py-6:.1f} {px-3:.1f},{py+8:.1f}"/></g>')
    person(s, 5.0, 8.4, "sage-l", "skin2")
    tree(s, 9.4, 9.0, 1.05)
    tree(s, 11.0, 10.8, 0.85, "terra")
    bench(s, 6.6, 10.2)
    lamp(s, 1.4, 7.6)
    return s

# ---------------------------------------------------------------- puentes y camino
def bridges():
    out = []
    for i in range(len(ORIGINS) - 1):
        (ox, oy), (nx, ny) = ORIGINS[i], ORIGINS[i + 1]
        y0, y1 = min(oy, ny) + 5, max(oy, ny) + 7
        x = ox + 12
        def slab(a, b, c, d):
            top = [(a, c, 0), (b, c, 0), (b, d, 0), (a, d, 0)]
            left = [(a, d, -0.3), (b, d, -0.3), (b, d, 0), (a, d, 0)]
            right = [(b, c, -0.3), (b, d, -0.3), (b, d, 0), (b, c, 0)]
            return (f'<polygon class="wood-l" points="{pts(left)}"/><polygon class="wood-r" points="{pts(right)}"/>'
                    f'<polygon class="road-t" points="{pts(top)}"/>')
        out.append(slab(x, x + 2, y0, y1))
    return out

def road_path():
    pts_ = []
    for i, (ox, oy) in enumerate(ORIGINS):
        if i == 0:
            pts_.append((ox + 6, oy + 6))
        else:
            pts_.append((ox + 6, oy + 6))
        if i < len(ORIGINS) - 1:
            nx, ny = ORIGINS[i + 1]
            pts_.append((ox + 13, oy + 6))
            pts_.append((ox + 13, ny + 6))
    proj = [P(x, y) for x, y in pts_]
    d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in proj)
    cum = [0.0]
    for a, b in zip(proj, proj[1:]):
        cum.append(cum[-1] + math.dist(a, b))
    centers = [(ox + 6, oy + 6) for ox, oy in ORIGINS]
    stops = [cum[pts_.index(c)] / cum[-1] for c in centers]
    return d, stops

# ---------------------------------------------------------------- ensamblar
def build():
    scenes = [madrid(), plaza(), campus(), aula(), gante(), correos()]
    brs = bridges()
    body = ""
    for i, s in enumerate(scenes):
        body += s.svg(i)
        if i < len(brs):
            body += f'<g class="bridge">{brs[i]}</g>'
    # límites
    xs, ys = [], []
    for ox, oy in ORIGINS:
        for (x, y, z) in ((ox, oy + 12, -1.5), (ox + 12, oy, 9), (ox + 12, oy + 12, -1.5), (ox, oy, 9)):
            px, py = P(x, y, z)
            xs.append(px); ys.append(py)
    m = 120
    vx, vy = min(xs) - m, min(ys) - m
    vw, vh = max(xs) - min(xs) + 2 * m, max(ys) - min(ys) + 2 * m
    defs = (
        '<defs>'
        '<filter id="paper" x="-10%" y="-10%" width="120%" height="130%">'
        '<feDropShadow dx="0" dy="10" stdDeviation="9" flood-color="#1F3A5F" flood-opacity=".16"/></filter>'
        '<linearGradient id="flag-es" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset=".3" stop-color="#C8102E"/><stop offset=".3" stop-color="#F1BF00"/>'
        '<stop offset=".62" stop-color="#F1BF00"/><stop offset=".62" stop-color="#C8102E"/></linearGradient>'
        '<linearGradient id="flag-en" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset=".26" stop-color="#012169"/><stop offset=".26" stop-color="#FFFFFF"/>'
        '<stop offset=".33" stop-color="#FFFFFF"/><stop offset=".33" stop-color="#C8102E"/>'
        '<stop offset=".5" stop-color="#C8102E"/><stop offset=".5" stop-color="#FFFFFF"/>'
        '<stop offset=".57" stop-color="#FFFFFF"/><stop offset=".57" stop-color="#012169"/></linearGradient>'
        '<linearGradient id="flag-nl" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset=".28" stop-color="#AE1C28"/><stop offset=".28" stop-color="#FFFFFF"/>'
        '<stop offset=".56" stop-color="#FFFFFF"/><stop offset=".56" stop-color="#21468B"/></linearGradient>'
        '</defs>'
    )
    road, stops = road_path()
    traveler = ('<g id="traveler" aria-hidden="true"><g class="walker"><g transform="scale(1.6)">'
                '<ellipse class="shadow" cx="0" cy="0" rx="7" ry="3"/>'
                '<rect class="ink-l" x="-4.5" y="-17" width="9" height="16" rx="4"/>'
                '<rect class="terra-l" x="1.5" y="-15" width="5" height="8" rx="2"/>'
                '<circle class="skin1" cx="0" cy="-21.5" r="4.5"/></g></g></g>')
    svg = (f'<svg class="world-svg" xmlns="http://www.w3.org/2000/svg" viewBox="{vx:.0f} {vy:.0f} {vw:.0f} {vh:.0f}" '
           f'width="{vw:.0f}" height="{vh:.0f}" data-vx="{vx:.0f}" data-vy="{vy:.0f}" role="img" '
           f'aria-label="Ilustración de un pequeño mundo de papel: Madrid, una plaza, el campus de la UAM, un aula, los canales de Gante y una oficina de correos, unidos por un camino.">'
           f'{defs}<g filter="url(#paper)">{body}</g>'
           f'<path id="road-path" d="{road}" data-stops="{",".join(f"{v:.5f}" for v in stops)}" fill="none" stroke="none"/>{traveler}</svg>')
    return svg

def inject():
    svg = build()
    idx = ROOT / "index.html"
    html = idx.read_text(encoding="utf-8")
    html = re.sub(r"<!-- world:start -->.*?<!-- world:end -->",
                  lambda _: f"<!-- world:start -->{svg}<!-- world:end -->", html, flags=re.S)
    idx.write_text(html, encoding="utf-8")
    light, dark, rules = css_vars()
    css = ROOT / "assets" / "site.css"
    block = ("/* world-colors:start */\n"
             ":root{" + ";".join(light) + "}\n"
             "@media (prefers-color-scheme:dark){:root{" + ";".join(dark) + "}}\n"
             + "\n".join(rules) + "\n/* world-colors:end */")
    text = css.read_text(encoding="utf-8")
    text = re.sub(r"/\* world-colors:start \*/.*?/\* world-colors:end \*/", lambda _: block, text, flags=re.S)
    css.write_text(text, encoding="utf-8")
    print(f"SVG: {len(svg)/1024:.0f} KB")

if __name__ == "__main__":
    inject()
