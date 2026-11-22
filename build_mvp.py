"""MVP-1: the real Waveshare ESP32-P4-WIFI6-Touch-LCD-5 (manufacturer STEP: PCB, components, glass)
assembled with battery, speaker, keys, SOUND/EXAM switch, wiring and the printed case.

Every case feature is placed from the manufacturer model itself (standoffs, side keys, USB-C, LED,
connectors, component heights), then checked by exact boolean interference.

Outputs (cad/out/):
  mvp1_assembly.step     full coloured assembly (open in FreeCAD / Fusion / Onshape / KiCad viewer)
  mvp1_case.step/.stl    printable case            mvp1_power_rod.stl   printable POWER push-rod
  mvp1_report.txt        all derived dimensions + interference results
  renders/mvp1_*.png     hero, back, side, bottom, open case, exploded, cutaway

Frame (the manufacturer's own): mm, X right, Y up (USB-C at the bottom), Z out of the screen.
"""
import os
import time

import cadquery as cq

from cadlib import Scene, export_assembly, interference, load_step_solids, lowest_under, sweep_wire

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
REN = os.path.join(OUT, "renders")
os.makedirs(REN, exist_ok=True)
T0 = time.time()
log = []


def say(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    log.append(s)


def find(solids, pred):
    return [s for s, _ in solids if pred(s.BoundingBox())]


def ctr(b):
    return ((b.xmin + b.xmax) / 2, (b.ymin + b.ymax) / 2, (b.zmin + b.zmax) / 2)


# ------------------------------------------------------------------ 1. manufacturer model
module = load_step_solids(os.path.join(HERE, "waveshare_lcd5.stp"))
say(f"Waveshare model: {len(module)} solids ({time.time()-T0:.0f}s)")
mb = cq.Compound.makeCompound([s for s, _ in module]).BoundingBox()
Z_FRONT = mb.zmax
glass = find(module, lambda b: b.xlen > 70 and b.ylen > 126)[0].BoundingBox()
pcb = find(module, lambda b: 64 < b.xlen < 65 and 118 < b.ylen < 119 and b.zlen < 2)[0].BoundingBox()
PCB_BACK = pcb.zmin
standoffs = [ctr(s.BoundingBox()) for s in find(module, lambda b: all(abs(v - 5.5) < 0.05 for v in (b.xlen, b.ylen, b.zlen)))]
ST_BOTTOM = min(s.BoundingBox().zmin for s in find(module, lambda b: all(abs(v - 5.5) < 0.05 for v in (b.xlen, b.ylen, b.zlen))))
side_keys = sorted((s.BoundingBox() for s in find(module, lambda b: b.xmax > 32.5 and b.zmax < -4 and b.ylen < 5)), key=lambda b: b.ymin)
pwr = side_keys[-1]                                   # POWER is the key nearest the C6 end
usb = sorted((s.BoundingBox() for s in find(module, lambda b: b.ymin < -63 and 9 < b.xlen < 10)), key=lambda b: b.xmin)
usb_uart = usb[-1]
led = find(module, lambda b: b.ymin < -61 and b.xlen < 2.5 and b.zlen < 1 and b.xmax < 0)[0].BoundingBox()
header = find(module, lambda b: 6 < b.xlen < 7 and 50 < b.ylen < 52)[0].BoundingBox()
spk_conn = find(module, lambda b: abs(b.xlen - 4.85) < 0.1 and abs(b.ylen - 5.76) < 0.1)[0].BoundingBox()
bat_conn = find(module, lambda b: abs(b.xlen - 5.2) < 0.1 and abs(b.ylen - 7.7) < 0.1)[0].BoundingBox()

say(f"overall module {mb.xlen:.2f} x {mb.ylen:.2f} x {mb.zlen:.2f} mm; glass front z={Z_FRONT:.2f}, PCB back z={PCB_BACK:.2f}")
say(f"standoffs (M2.5, bottom z={ST_BOTTOM:.2f}): " + ", ".join(f"({x:.2f},{y:.2f})" for x, y, _ in standoffs))
say(f"side keys y-centres: " + ", ".join(f"{(b.ymin+b.ymax)/2:.2f}" for b in side_keys) + f"  (POWER = {(pwr.ymin+pwr.ymax)/2:.2f}, actuator x={pwr.xmax:.2f}, z={(pwr.zmin+pwr.zmax)/2:.2f})")
say(f"USB-C UART centre x={(usb_uart.xmin+usb_uart.xmax)/2:.2f} z={(usb_uart.zmin+usb_uart.zmax)/2:.2f}; LED x={(led.xmin+led.xmax)/2:.2f}")
say(f"header x {header.xmin:.2f}..{header.xmax:.2f} y {header.ymin:.2f}..{header.ymax:.2f} bottom z={header.zmin:.2f}")

# ------------------------------------------------------------------ 2. derived case geometry
CLR, WALL, FLOOR, LIP = 0.3, 2.0, 2.0, 0.4
IW, IH = glass.xlen + 2 * CLR, glass.ylen + 2 * CLR
OW, OH = IW + 2 * WALL, IH + 2 * WALL
XI = IW / 2                                           # inner face of the right wall
Z_RIM = Z_FRONT + LIP

BAT = (40.0, 60.0, 7.2)                               # 704060 cell (model); pocket allows 41 x 61 x 7.5
BX0, BY1 = -22.6, 55.5
BX1, BY0 = BX0 + 41.0, BY1 - 61.0
bat_low = lowest_under(module, BX0, BX1, BY0, BY1)
PLUG_H = 2.5
FLOOR_TOP = min(bat_low - 0.8 - 7.5 - 0.5, header.zmin - PLUG_H - 1.5)
Z_BACK = FLOOR_TOP - FLOOR
say(f"lowest part over the battery z={bat_low:.2f} -> case floor top z={FLOOR_TOP:.2f}, back z={Z_BACK:.2f}")
say(f"CASE OUTSIDE: {OW:.1f} x {OH:.1f} x {Z_RIM - Z_BACK:.1f} mm")

KEY_Z = FLOOR_TOP + 2.0 + 3.0                         # tactile / slide pockets: centre height
TACT = (3.5, 6.0, 6.0)                                # body depth (X), width (Y), height (Z); stem d3.5 x 3.5
SLIDE = (4.4, 8.6, 4.4)
keys = {"VOL+": 45.0, "VOL-": 25.0, "HOME": -18.0}
SLIDE_Y = -43.0
for name, y in list(keys.items()) + [("SLIDE", SLIDE_Y)]:
    low = lowest_under(module, XI - 6, XI, y - 5, y + 5)
    assert KEY_Z + 3.0 < low - 0.3, f"{name} pocket hits the board (top {KEY_Z+3:.2f} vs {low:.2f})"

# speaker: search the lower half for the deepest free spot (its top must clear the board by 0.3 mm)
SPK = (20.0, 30.0, 6.8)
best = None
bosses = [(x, y) for x, y, _ in standoffs]
for w, h in ((SPK[0], SPK[1]), (SPK[1], SPK[0])):
    x0 = -22.0
    while x0 + w + 0.6 <= 27.4:
        y0 = -62.5
        while y0 + h + 0.6 <= BY0 - 1.0:
            r = (x0, x0 + w + 0.6, y0, y0 + h + 0.6)
            ok = all(not (r[0] - 4 < bx < r[1] + 4 and r[2] - 4 < by < r[3] + 4) for bx, by in bosses)
            if ok:
                clear = lowest_under(module, *r) - (FLOOR_TOP + SPK[2])
                if clear >= 0.3:
                    d = abs((r[0] + r[1]) / 2 - (spk_conn.xmin + spk_conn.xmax) / 2) + abs((r[2] + r[3]) / 2 - (spk_conn.ymin + spk_conn.ymax) / 2)
                    if best is None or d < best[0]:
                        best = (d, r, w, h, clear)
            y0 += 1.0
        x0 += 1.0
assert best, "no room for the speaker"
_, SPK_R, SPK_W, SPK_H, spk_clear = best
say(f"speaker placed at x {SPK_R[0]:.1f}..{SPK_R[1]:.1f}, y {SPK_R[2]:.1f}..{SPK_R[3]:.1f} ({SPK_W:.0f}x{SPK_H:.0f}), {spk_clear:.2f} mm under the board")


def rbox(w, h, d, r, z0, cx=0.0, cy=0.0):
    return cq.Workplane("XY").workplane(offset=z0).center(cx, cy).rect(w, h).extrude(d).edges("|Z").fillet(r)


def cyl(d, h, p, axis=(0, 0, 1)):
    return cq.Workplane("XY").add(cq.Solid.makeCylinder(d / 2, h, cq.Vector(*p), cq.Vector(*axis)))


def box(x0, x1, y0, y1, z0, z1):
    return cq.Workplane("XY").add(cq.Solid.makeBox(x1 - x0, y1 - y0, z1 - z0, cq.Vector(x0, y0, z0)))


# ------------------------------------------------------------------ 3. case
RENDER_ONLY = bool(os.environ.get("RENDER_ONLY"))
sx0, sx1, sy0, sy1 = SPK_R
PWR_Y, PWR_Z = (pwr.ymin + pwr.ymax) / 2, (pwr.zmin + pwr.zmax) / 2
if RENDER_ONLY:
    case = cq.importers.importStep(os.path.join(OUT, "mvp1_case.step"))
else:
    shell = rbox(OW, OH, Z_RIM - Z_BACK, 3.0 + CLR + WALL, Z_BACK)
    shell = shell.cut(rbox(IW, IH, Z_RIM - FLOOR_TOP + 1, 3.0 + CLR, FLOOR_TOP))
    try:
        shell = shell.faces("<Z").edges().fillet(1.5)
        shell = shell.faces(">Z").chamfer(0.4)
    except Exception as e:
        say("edge rounding skipped:", e)

    for x, y, _ in standoffs:                             # bosses up to the board's own M2.5 standoffs
        shell = shell.union(cyl(6.5, ST_BOTTOM - FLOOR_TOP + 0.01, (x, y, FLOOR_TOP - 0.01)))
        shell = shell.cut(cyl(2.8, ST_BOTTOM - Z_BACK + 2, (x, y, Z_BACK - 1)))
        shell = shell.cut(cyl(5.0, 1.8, (x, y, Z_BACK - 0.01)))


    def pocket(y, body, slot_z):
        dx, wy, hz = body
        x0 = XI - dx - 1.6
        p = box(x0, XI + 0.01, y - wy / 2 - 1.2, y + wy / 2 + 1.2, FLOOR_TOP - 0.01, slot_z + hz / 2)
        p = p.cut(box(XI - dx - 0.1, XI + 0.2, y - wy / 2 - 0.15, y + wy / 2 + 0.15, slot_z - hz / 2, slot_z + hz))
        p = p.cut(box(x0 - 1, x0 + 1.7, y - 2, y + 2, slot_z - hz / 2 + 0.8, slot_z + hz))   # legs / wires
        return p


    for y in keys.values():
        shell = shell.union(pocket(y, TACT, KEY_Z)).cut(cyl(4.0, WALL + 2, (XI - 1, y, KEY_Z), (1, 0, 0)))
    shell = shell.union(pocket(SLIDE_Y, SLIDE, KEY_Z)).cut(box(XI - 1, XI + WALL + 1, SLIDE_Y - 2.15, SLIDE_Y + 2.15, KEY_Z - 1.2, KEY_Z + 1.2))
    PWR_Y, PWR_Z = (pwr.ymin + pwr.ymax) / 2, (pwr.zmin + pwr.zmax) / 2
    shell = shell.cut(cyl(3.8, WALL + 2, (XI - 1, PWR_Y, PWR_Z), (1, 0, 0)))

    # speaker frame + grille, battery corner stops
    sx0, sx1, sy0, sy1 = SPK_R
    fr = box(sx0 - 1.2, sx1 + 1.2, sy0 - 1.2, sy1 + 1.2, FLOOR_TOP - 0.01, FLOOR_TOP + 4).cut(box(sx0, sx1, sy0, sy1, FLOOR_TOP - 1, FLOOR_TOP + 6))
    fr = fr.cut(box((sx0 + sx1) / 2 - 3, (sx0 + sx1) / 2 + 3, sy1 - 0.5, sy1 + 2, FLOOR_TOP + 1, FLOOR_TOP + 6))
    shell = shell.union(fr)
    grille, x = [], sx0 + 2.5
    while x <= sx1 - 2.5:
        y = sy0 + 2.5
        while y <= sy1 - 2.5:
            grille.append(cq.Solid.makeCylinder(0.8, FLOOR + 2, cq.Vector(x, y, Z_BACK - 1)))
            y += 3.0
        x += 3.0
    shell = shell.cut(cq.Workplane("XY").add(cq.Compound.makeCompound(grille)))
    for cx_, cy_, sx, sy in ((BX0, BY0, 1, 1), (BX1, BY0, -1, 1), (BX0, BY1, 1, -1), (BX1, BY1, -1, -1)):
        L, f = 6.0, 1.2
        xa = cx_ - f if sx > 0 else cx_ - L + f
        ya = cy_ - f if sy > 0 else cy_
        shell = shell.union(box(xa, xa + L, ya, ya + f, FLOOR_TOP - 0.01, FLOOR_TOP + 2.5))
        xb = cx_ - f if sx > 0 else cx_
        yb = cy_ - f if sy > 0 else cy_ - L + f
        shell = shell.union(box(xb, xb + f, yb, yb + L, FLOOR_TOP - 0.01, FLOOR_TOP + 2.5))

    # openings: USB-C (UART: charge + flash), charge LED; OTG port and microSD stay sealed
    ux, uz = (usb_uart.xmin + usb_uart.xmax) / 2, (usb_uart.zmin + usb_uart.zmax) / 2
    usb_cut = box(ux - 6.0, ux + 6.0, -OH / 2 - 1, -IH / 2 + 1, uz - 3.25, uz + 3.25).edges("|Y").fillet(2.4)
    shell = shell.cut(usb_cut)
    shell = shell.cut(cyl(2.0, WALL + 2, ((led.xmin + led.xmax) / 2, -IH / 2 + 1, (led.zmin + led.zmax) / 2), (0, -1, 0)))

    try:                                                  # model name on the back, reads from behind
        tp = cq.Plane(origin=(0, 6, Z_BACK), xDir=(-1, 0, 0), normal=(0, 0, -1))
        txt = cq.Workplane(tp).text("TamilDict MVP-1", 5.5, -0.6, combine=False, kind="bold", halign="center", valign="center")
        shell = shell.cut(txt)
    except Exception as e:
        say("back lettering skipped:", e)
    case = shell
say(f"case built ({time.time()-T0:.0f}s), volume {case.val().Volume()/1000:.1f} cm^3")

# ------------------------------------------------------------------ 4. added parts
battery = rbox(BAT[0], BAT[1], BAT[2], 1.5, FLOOR_TOP + 0.5, (BX0 + BX1) / 2, (BY0 + BY1) / 2)
speaker = box(sx0 + 0.3, sx1 - 0.3, sy0 + 0.3, sy1 - 0.3, FLOOR_TOP, FLOOR_TOP + SPK[2])
switches = None
for y in keys.values():
    body = box(XI - TACT[0], XI, y - 3, y + 3, KEY_Z - 3, KEY_Z + 3)
    stem = cyl(3.5, 3.5, (XI, y, KEY_Z), (1, 0, 0))
    s = body.union(stem)
    switches = s if switches is None else switches.union(s)
slide = box(XI - SLIDE[0], XI, SLIDE_Y - SLIDE[1] / 2, SLIDE_Y + SLIDE[1] / 2, KEY_Z - SLIDE[2] / 2, KEY_Z + SLIDE[2] / 2)
slide = slide.union(box(XI, XI + WALL + 1.0, SLIDE_Y - 0.75 - 0.6, SLIDE_Y + 0.75 - 0.6, KEY_Z - 0.9, KEY_Z + 0.9))
rod_nub = 1.6
rod_x0 = pwr.xmax + 0.3
rod = cyl(2.5, rod_nub + 0.01, (rod_x0, PWR_Y, PWR_Z), (1, 0, 0))
rod = rod.union(cyl(5.5, 1.0, (rod_x0 + rod_nub, PWR_Y, PWR_Z), (1, 0, 0)))
rod = rod.union(cyl(3.3, 1.0 + WALL + 0.8, (rod_x0 + rod_nub, PWR_Y, PWR_Z), (1, 0, 0)))
screws = None
for x, y, _ in standoffs:
    sc = cyl(4.5, 1.7, (x, y, Z_BACK + 0.05)).union(cyl(2.4, 10.0, (x, y, Z_BACK + 1.7)))
    screws = sc if screws is None else screws.union(sc)
hx = (header.xmin + header.xmax) / 2
hy = header.ymax - 1.27 - 6 * 2.54                    # pins 11-16 = pairs 6-8 from pin 1 (top end)
plug = box(hx - 2.54, hx + 2.54, hy - 3.81, hy + 3.81, header.zmin - PLUG_H, header.zmin)

wires, wire_names = [], []
zf0 = FLOOR_TOP + 0.6
ends = [("VOL+", keys["VOL+"], XI - TACT[0] - 1.6 - 0.4), ("VOL-", keys["VOL-"], XI - TACT[0] - 1.6 - 0.4),
        ("HOME", keys["HOME"], XI - TACT[0] - 1.6 - 0.4), ("SOUND sense", SLIDE_Y, XI - SLIDE[0] - 1.6 - 0.4),
        ("GND", SLIDE_Y - 2.5, XI - SLIDE[0] - 1.6 - 0.4)]
for i, (n, y, xe) in enumerate(ends):
    z = zf0 + i * 1.05
    px = hx - 1.27 + (i % 2) * 2.54
    py = hy - 2.54 + (i // 2) * 2.54
    pts = [(px, py, header.zmin - PLUG_H - 0.2), (px, py, z), (-23.9, py, z), (-23.9, 58.8 - i * 0.0, z),
           (23.5, 58.8, z), (23.5, 47.0, z), (29.0 - i * 0.0, 47.0, z), (29.0, y, z), (xe, y, KEY_Z if n != "GND" else KEY_Z - 1.5)]
    wires.append(sweep_wire(pts, 1.0))
    wire_names.append(n)
scx, scy = (spk_conn.xmin + spk_conn.xmax) / 2, (spk_conn.ymin + spk_conn.ymax) / 2
zs = FLOOR_TOP + SPK[2] + 0.2 if False else FLOOR_TOP + 1.5
spk_mid = ((sx0 + sx1) / 2, sy1 + 0.6)
wires.append(sweep_wire([(spk_mid[0] + 1, sy1 - 0.3, FLOOR_TOP + 3.5), (spk_mid[0] + 1, sy1 + 2.0, FLOOR_TOP + 3.5), (28.2, sy1 + 2.0, FLOOR_TOP + 3.5),
                         (28.2, SLIDE_Y + 1.5, FLOOR_TOP + 3.5), (XI - SLIDE[0] - 1.6 - 0.4, SLIDE_Y + 1.5, KEY_Z + 1.0)], 1.0))
wire_names.append("speaker + (via slide pole A)")
wires.append(sweep_wire([(spk_mid[0] - 1, sy1 - 0.3, FLOOR_TOP + 3.5), (spk_mid[0] - 1, sy1 + 3.2, FLOOR_TOP + 3.5),
                         (scx, sy1 + 3.2, FLOOR_TOP + 3.5), (scx, scy, FLOOR_TOP + 3.5), (scx, scy, spk_conn.zmin - 0.2)], 1.0))
wire_names.append("speaker - / pole A return to SPK")
bcx, bcy = (bat_conn.xmin + bat_conn.xmax) / 2, (bat_conn.ymin + bat_conn.ymax) / 2
zb = FLOOR_TOP + 1.2
wires.append(sweep_wire([(BX0 + 3, BY0 + 0.3, zb), (BX0 + 3, BY0 - 3.0, zb), (BX0 + 3, -20.0, zb), (bcx, -20.0, zb), (bcx, bcy, zb), (bcx, bcy, bat_conn.zmin - 0.2)], 1.2))
wire_names.append("battery to BAT")
say(f"parts + {len(wires)} wires built ({time.time()-T0:.0f}s)")

# ------------------------------------------------------------------ 5. interference check
if not RENDER_ONLY:
  exec(compile(r'''
named = [("case", case), ("battery", battery), ("speaker", speaker), ("tactile switches", switches), ("slide switch", slide),
         ("POWER rod", rod), ("screws", screws), ("header plug", plug)] + [(f"wire: {n}", w) for n, w in zip(wire_names, wires)]
hits = interference(named, module)
SOFT = {"header plug", "slide switch", "tactile switches", "speaker", "battery"}


def expected(a, b):
    """Contacts that are meant to happen: screws threading into the board's standoffs, wires
    ending in/touching the part they are soldered to, and wires touching each other in a bundle."""
    if a == "screws" and b.startswith("module"):
        return True
    wa, wb = a.startswith("wire"), b.startswith("wire")
    return (wa and wb) or (wa and b in SOFT) or (wb and a in SOFT)


real = [h for h in hits if not expected(h[0], h[1])]
say(f"interference check: {len(hits)} contacts, {len(real)} unexpected")
for a, b, v in hits:
    say(f"  {'!!' if (a, b, v) in real else 'ok'} {a}  x  {b}: {v:.3f} mm^3")

# ------------------------------------------------------------------ 6. export
cq.exporters.export(case, os.path.join(OUT, "mvp1_case.step"))
cq.exporters.export(case, os.path.join(OUT, "mvp1_case.stl"), tolerance=0.02, angularTolerance=0.1)
cq.exporters.export(rod, os.path.join(OUT, "mvp1_power_rod.stl"), tolerance=0.01, angularTolerance=0.1)
by_color = {}
for s, c in module:
    by_color.setdefault(tuple(round(v, 3) for v in c), []).append(s)
parts = [(f"waveshare_{i}", sols, c) for i, (c, sols) in enumerate(by_color.items())]
parts += [("case", case, (0.95, 0.94, 0.91)), ("battery_704060", battery, (0.72, 0.74, 0.78)), ("speaker_2030", speaker, (0.1, 0.1, 0.1)),
          ("tactile_switches", switches, (0.15, 0.15, 0.15)), ("slide_switch", slide, (0.2, 0.2, 0.2)), ("power_rod", rod, (0.88, 0.48, 0.12)),
          ("screws_M2_5x10", screws, (0.3, 0.3, 0.32)), ("header_plug", plug, (0.05, 0.05, 0.05))]
wcols = [(0.85, 0.15, 0.15), (0.15, 0.45, 0.85), (0.95, 0.75, 0.1), (0.2, 0.7, 0.3), (0.1, 0.1, 0.1), (0.85, 0.15, 0.15), (0.1, 0.1, 0.1), (0.85, 0.15, 0.15)]
parts += [(f"wire_{i}", w, wcols[i % len(wcols)]) for i, w in enumerate(wires)]
export_assembly(parts, os.path.join(OUT, "mvp1_assembly.step"), "TamilDict_MVP1")
say(f"STEP written ({time.time()-T0:.0f}s)")

''', 'checks', 'exec'))

# ------------------------------------------------------------------ 7. renders
def style(c, b):
    if b.xlen > 70 and b.ylen > 126:
        return (0.02, 0.02, 0.025), 0.9, 80          # cover glass
    if 64 < b.xlen < 65 and 118 < b.ylen < 119:
        return (0.08, 0.22, 0.52), 0.2, 15          # PCB
    return c, 0.35, 30


def build_scene(cut_y=None):
    sc = Scene()
    keep = (lambda b: True) if cut_y is None else (lambda b: b.ymin < cut_y)
    cutter = None if cut_y is None else cq.Solid.makeBox(400, 400, 400, cq.Vector(-200, cut_y, -200))

    def clip(shape):
        if cutter is None:
            return shape
        b = shape.BoundingBox()
        if b.ymin >= cut_y:
            return None
        if b.ymax <= cut_y:
            return shape
        try:
            return shape.cut(cutter)
        except Exception:
            return shape

    for s, c in module:
        b = s.BoundingBox()
        if not keep(b):
            continue
        s2 = clip(s)
        if s2 is None:
            continue
        col, spec, gl = style(c, b)
        sc.add("module", s2, col, spec, gl, tol=0.04)
    va_w, va_h = glass.xlen - 2 * 4.21, glass.ylen - 2 * 8.29
    if cut_y is None:
        z = Z_FRONT + 0.02
        sc.add_image_plane("module", os.path.join(HERE, "tex", "screen_home.png"),
                           (-va_w / 2, -va_h / 2, z), (va_w / 2, -va_h / 2, z), (-va_w / 2, va_h / 2, z))
    for name, shp, col in [("case", case, (0.95, 0.945, 0.92)), ("inside", battery, (0.72, 0.74, 0.78)), ("inside", speaker, (0.12, 0.12, 0.12)),
                           ("inside", switches, (0.16, 0.16, 0.17)), ("inside", slide, (0.2, 0.2, 0.22)), ("inside", rod, (0.9, 0.5, 0.12)),
                           ("inside", plug, (0.06, 0.06, 0.06)), ("screws", screws, (0.35, 0.35, 0.37))]:
        s2 = clip(shp.val())
        if s2 is not None:
            sc.add(name, s2, col, 0.25 if name == "case" else 0.4, 15 if name == "case" else 40, tol=0.03)
    for i, w in enumerate(wires):
        s2 = clip(w.val())
        if s2 is not None:
            sc.add("inside", s2, wcols[i % len(wcols)], 0.5, 40, tol=0.03)
    return sc


sc = build_scene()
say(f"scene tessellated ({time.time()-T0:.0f}s)")
D = 400
shots = [("mvp1_hero.png", (0.42, 0.22, 0.88), (0, 0, 0), 1.0),
         ("mvp1_front.png", (0.0, 0.0, 1.0), (0, 0, 0), 1.0),
         ("mvp1_back.png", (-0.38, 0.18, -0.9), (0, 0, -6), 1.0),
         ("mvp1_right_side.png", (0.97, 0.06, 0.22), (34, 0, -6), 1.0),
         ("mvp1_bottom.png", (0.25, -0.85, 0.46), (0, -55, -6), 1.9)]
for name, d, f, z in shots:
    sc.shoot(os.path.join(REN, name), [f[i] + d[i] * D for i in range(3)], f, zoom=z)
sc.show("module", False)                               # open case: everything that goes in the tub
sc.shoot(os.path.join(REN, "mvp1_open_case.png"), [0.12 * D, -0.28 * D, 0.95 * D], (0, 0, -8), zoom=1.0)
sc.show("module", True)
sc.offset("inside", dz=30)
sc.offset("module", dz=62)
sc.offset("screws", dz=-22)
sc.shoot(os.path.join(REN, "mvp1_exploded.png"), [0.78 * 520, 0.32 * 520, 0.55 * 520], (0, 0, 22), zoom=1.0)
say(f"renders written ({time.time()-T0:.0f}s)")

cut_y = (keys["VOL-"] + BY0) / 2 + 8                   # section through battery, P4 module and a key
sc2 = build_scene(cut_y)
sc2.shoot(os.path.join(REN, "mvp1_cutaway.png"), [70, cut_y + 230, 60], (0, cut_y, -6), up=(0, 0, 1), zoom=1.0)
sc2.shoot(os.path.join(REN, "mvp1_cutaway_detail.png"), [40, cut_y + 120, 15], (18, cut_y, -6), up=(0, 0, 1), zoom=1.0)
say(f"cutaway written at y={cut_y:.1f} ({time.time()-T0:.0f}s)")

with open(os.path.join(OUT, "mvp1_report.txt" if not RENDER_ONLY else "mvp1_render_log.txt"), "w") as f:
    f.write("\n".join(log) + "\n")
