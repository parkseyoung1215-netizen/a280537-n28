"""Design engine: turns a cabinet/bookshelf spec into real parts, checks that the
design actually works, and produces a cut list you can hand to a store's
cutting service.

The AI (later) only turns words into a spec. Everything below is plain,
checkable arithmetic, so the numbers never come from a guess.

Construction (simple and common for DIY):
- two sides run the full height
- top, bottom and fixed shelves sit between the sides, screwed through the sides
- a thin back panel is screwed onto the back (it also keeps the box square)
All sizes are in millimetres.
"""
from dataclasses import dataclass, field, asdict
import json
import math
import sys


@dataclass
class Spec:
    width: int                 # outside width
    height: int                # outside height
    depth: int                 # outside depth, back panel included
    shelves: int = 3           # fixed shelves between top and bottom
    thickness: int = 18        # main board thickness
    back_thickness: int = 4    # back panel (HDF) thickness
    load_kg_per_shelf: float = 20.0
    material: str = "birch_plywood"
    min_gap: int = 0           # smallest clear height needed per compartment (0 = no rule)
    space_width: int = 0       # space where it must fit (0 = no limit)
    space_height: int = 0
    space_depth: int = 0


# Stiffness (modulus of elasticity, MPa). Conservative values for each board type.
MATERIALS = {
    "birch_plywood": {"E": 7000, "name": "Birch plywood (Multiplex)"},
    "pine_plywood": {"E": 5500, "name": "Pine plywood"},
    "chipboard": {"E": 2500, "name": "Chipboard (Spanplatte)"},
    "mdf": {"E": 3000, "name": "MDF"},
}
SHEET = (2500, 1250)   # common full sheet size in German DIY stores
KERF = 4               # saw blade width lost per cut
MIN_CUT = 50           # store cutting services often refuse very narrow strips
SAG_LIMIT = 1 / 600    # woodworking rule of thumb: sag under 1/600 of the span


@dataclass
class Part:
    name: str
    length: int    # the longer side
    width: int
    thickness: int
    qty: int


@dataclass
class Result:
    spec: dict
    parts: list
    checks: list = field(default_factory=list)   # (level, message); level: ok / warn / fail
    shelf_positions: list = field(default_factory=list)
    sheets: list = field(default_factory=list)
    hardware: dict = field(default_factory=dict)

    @property
    def ok(self):
        return not any(level == "fail" for level, _ in self.checks)


def make_parts(s: Spec):
    t, bt = s.thickness, s.back_thickness
    inner_w = s.width - 2 * t
    carcass_d = s.depth - bt
    parts = [
        Part("Side", s.height, carcass_d, t, 2),
        Part("Top / bottom", inner_w, carcass_d, t, 2),
    ]
    if s.shelves:
        parts.append(Part("Shelf", inner_w, carcass_d, t, s.shelves))
    parts.append(Part("Back panel", s.height, s.width, bt, 1))
    for p in parts:   # store as long side x short side
        p.length, p.width = max(p.length, p.width), min(p.length, p.width)
    return parts


def shelf_sag_mm(span, depth, t, load_kg, E):
    """Mid-span sag of a shelf under an evenly spread load (simply supported beam)."""
    w = load_kg * 9.81 / span            # N per mm of span
    I = depth * t ** 3 / 12              # mm^4
    return 5 * w * span ** 4 / (384 * E * I)


def check(s: Spec, parts):
    c = []
    t = s.thickness
    inner_w = s.width - 2 * t
    inner_h = s.height - 2 * t - s.shelves * t
    gaps = s.shelves + 1

    # 1. basic geometry
    if inner_w <= 0 or inner_h <= 0 or s.depth <= s.back_thickness:
        c.append(("fail", "The outside size is too small for this board thickness and number of shelves."))
        return c
    gap = inner_h / gaps
    if gap < 80:
        c.append(("fail", f"Compartments would be only {gap:.0f} mm high. Use fewer shelves or a taller cabinet."))
    elif s.min_gap and gap < s.min_gap:
        c.append(("fail", f"Compartments are {gap:.0f} mm high but you need {s.min_gap} mm. "
                          f"At most {max(0, int((s.height - 2 * t + t) // (s.min_gap + t)) - 1)} shelves fit."))
    else:
        c.append(("ok", f"{gaps} compartments, each {gap:.0f} mm high."))

    # 2. fits the space
    for name, size, space, margin in (("width", s.width, s.space_width, 10),
                                      ("height", s.height, s.space_height, 10),
                                      ("depth", s.depth, s.space_depth, 0)):
        if space:
            if size + margin > space:
                c.append(("fail", f"Too big for the space: {name} {size} mm, space {space} mm "
                                  f"(keep {margin} mm to slide it in)."))
            else:
                c.append(("ok", f"Fits the space in {name} ({space - size} mm to spare)."))

    # 3. shelf sag
    mat = MATERIALS[s.material]
    if True:   # top/bottom carry load too, so always check
        sag = shelf_sag_mm(inner_w, s.depth - s.back_thickness, t, s.load_kg_per_shelf, mat["E"])
        limit = inner_w * SAG_LIMIT
        if sag > 2 * limit:
            c.append(("fail", f"Shelves will visibly bend: {sag:.1f} mm sag under {s.load_kg_per_shelf:g} kg "
                              f"(limit {limit:.1f} mm). Make it narrower, use thicker boards, or add a divider."))
        elif sag > limit:
            c.append(("warn", f"Shelves may bend a little over time: {sag:.1f} mm sag (limit {limit:.1f} mm)."))
        else:
            c.append(("ok", f"Shelves stay flat: {sag:.1f} mm sag under {s.load_kg_per_shelf:g} kg (limit {limit:.1f} mm)."))

    # 4. tipping over
    if s.height > 1000 or s.height / s.depth > 3:
        c.append(("warn", "Tall or shallow: fix it to the wall with an anti-tip bracket."))
    else:
        c.append(("ok", "Low and deep enough to stand without wall fixing."))

    # 5. can the store cut it?
    for p in parts:
        if p.width < MIN_CUT:
            c.append(("warn", f"'{p.name}' is only {p.width} mm wide; some store cutting services refuse strips under {MIN_CUT} mm."))
        if p.length > SHEET[0] or p.width > SHEET[1]:
            c.append(("fail", f"'{p.name}' ({p.length} x {p.width} mm) is bigger than a full sheet {SHEET[0]} x {SHEET[1]} mm."))
    return c


def shelf_positions(s: Spec):
    """Height of the top face of each shelf, measured from the bottom of the cabinet."""
    t = s.thickness
    gap = (s.height - 2 * t - s.shelves * t) / (s.shelves + 1)
    return [round(t + i * (gap + t)) for i in range(1, s.shelves + 1)]


def nest(parts, thickness):
    """Simple strip packing of parts of one thickness onto full sheets.

    Strips run across the sheet's long side; parts may be rotated.
    Good enough to estimate how many sheets to buy.
    """
    pieces = []
    for p in parts:
        if p.thickness == thickness:
            pieces += [(p.name, p.length, p.width)] * p.qty
    pieces.sort(key=lambda x: (-x[2], -x[1]))   # widest first
    L, W = SHEET
    sheets = []   # each: list of strips; strip = [y, height, used_x, items]
    for name, pl, pw in pieces:
        placed = False
        for sheet in sheets:
            for strip in sheet:
                y, h, x, items = strip
                for a, b in ((pl, pw), (pw, pl)):
                    if b <= h and x + a <= L:
                        items.append((name, x, y, a, b))
                        strip[2] = x + a + KERF
                        placed = True
                        break
                if placed:
                    break
            if placed:
                break
            used_h = sum(st[1] + KERF for st in sheet)
            for a, b in ((pl, pw), (pw, pl)):
                if a <= L and used_h + b <= W:
                    sheet.append([used_h, b, a + KERF, [(name, 0, used_h, a, b)]])
                    placed = True
                    break
            if placed:
                break
        if not placed:
            a, b = (pl, pw) if pl <= L and pw <= W else (pw, pl)
            sheets.append([[0, b, a + KERF, [(name, 0, 0, a, b)]]])
    return [[it for strip in sheet for it in strip[3]] for sheet in sheets]


def hardware(s: Spec, parts):
    t = s.thickness
    per_joint = 3 if s.depth > 300 else 2
    boards_between = 2 + s.shelves                     # top, bottom, shelves
    screw_len = 50 if t >= 18 else 40
    back_perimeter = 2 * (s.width + s.height)
    return {
        f"Wood screws 4 x {screw_len} mm": boards_between * 2 * per_joint,
        "Back panel screws 3 x 16 mm": math.ceil(back_perimeter / 150)
                                       + (s.shelves * math.ceil(s.width / 200)),
        "Anti-tip wall bracket": 1 if (s.height > 1000 or s.height / s.depth > 3) else 0,
    }


def design(s: Spec) -> Result:
    parts = make_parts(s)
    r = Result(spec=asdict(s), parts=[asdict(p) for p in parts])
    r.checks = check(s, parts)
    if r.ok:
        r.shelf_positions = shelf_positions(s)
        r.sheets = [{"thickness": th, "layout": nest(parts, th)}
                    for th in sorted({p.thickness for p in parts}, reverse=True)]
        r.hardware = hardware(s, parts)
    return r


def text_report(r: Result) -> str:
    s = r.spec
    mat = MATERIALS[s["material"]]["name"]
    out = [f"Cabinet {s['width']} x {s['height']} x {s['depth']} mm (W x H x D), {s['shelves']} shelves, {mat}",
           "", "CHECKS"]
    marks = {"ok": "[ok]  ", "warn": "[warn]", "fail": "[FAIL]"}
    out += [f"  {marks[l]} {m}" for l, m in r.checks]
    if not r.ok:
        out += ["", "Design rejected: fix the [FAIL] items first."]
        return "\n".join(out)
    out += ["", "CUT LIST (give this to the store's cutting service)"]
    for p in r.parts:
        out.append(f"  {p['qty']} x {p['length']} x {p['width']} mm, {p['thickness']} mm thick  ({p['name']})")
    out += ["", "SHEETS TO BUY"]
    for sh in r.sheets:
        out.append(f"  {len(sh['layout'])} sheet(s) {SHEET[0]} x {SHEET[1]} mm, {sh['thickness']} mm thick")
    out += ["", "HARDWARE"]
    out += [f"  {n} x {k}" for k, n in r.hardware.items() if n]
    out += ["", "SHELF HEIGHTS (top of shelf, from the bottom of the cabinet): "
            + ", ".join(f"{h} mm" for h in r.shelf_positions)]
    return "\n".join(out)


if __name__ == "__main__":
    spec = Spec(**json.load(open(sys.argv[1])))
    print(text_report(design(spec)))
