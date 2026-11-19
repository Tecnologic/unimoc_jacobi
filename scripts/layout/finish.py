"""Silkscreen: reference designators, connector labels, board marking.

A designator stands right next to its part only where it can belong to no
other part: in line with the part, touching nothing closer. Dense groups get a
framed block of their designators next to them, in the same arrangement as the
parts (SECTIONS); the gate networks of the power board and a few single parts
have fixed spots. Values and other footprint texts stay on the fabrication
layer only. Connectors carry their function on the top side; the bottom side
of the logic board names every pin of the external connectors where the wires
are soldered or plugged in (not the headers to the power board).
"""
import math

import numpy as np
import pcbnew
from PIL import Image, ImageDraw

MM = pcbnew.FromMM
TM = pcbnew.ToMM
G = 0.1
X0, Y0, X1, Y1 = 178.0, 57.0, 370.0, 140.0
NX, NY = int((X1 - X0) / G) + 1, int((Y1 - Y0) / G) + 1
CHAR = 0.9           # advance of a character relative to the text height

LABEL = {   # connector -> what it is
    'J501': 'ENABLE', 'J1103': 'CAN IN', 'J1104': 'CAN OUT', 'J601': 'AIN', 'J602': 'USB', 'J701': 'MOT NTC',
    'J1101': 'HALL', 'P1101': 'SWD', 'JP601': 'BOOT', 'J105': '+BATT', 'J109': 'GND', 'J106': 'PHASE A',
    'J107': 'PHASE B', 'J108': 'PHASE C', 'J103': 'PWM', 'J104': 'ADC', 'J110': 'VSENSE',
}
BOTTOM = {  # external connectors of the logic board, seen from the bottom: pin -> meaning
    'J501': ['BATT+', 'VIN LOGIC', 'PWM EN+', 'PWM EN-'],
    'J1103': ['CAN GND', 'CAN L', 'CAN H', 'NC'], 'J1104': ['CAN GND', 'CAN L', 'CAN H', 'NC'],
    'J601': ['GND', 'DCC', 'ACC', '+3V3'], 'J701': ['GND', 'NTC'],
    'J1101': ['GND', 'HALL A', 'HALL B', 'HALL C', '+5V'],
}
BOTTOM_LABEL = {'J501': 'ENABLE', 'J1103': 'CAN IN', 'J1104': 'CAN OUT', 'J601': 'AIN', 'J701': 'MOT NTC',
                'J1101': 'HALL', 'J602': 'USB', 'P1101': 'SWD'}
SWD = {'1': '3V3', '2': 'DIO', '3': 'GND', '4': 'CLK', '5': 'GND', '6': 'SWO', '10': 'RST'}
LEDS = ('D1101', 'D1102', 'D1103', 'D1104')       # names (values) under the LEDs
# dense groups: their designators go into one framed block in the same arrangement, inside the area
# given (x0, y0, x1, y1); 'rows' lists each row of parts as a line, 'cols' each column upright
SECTIONS = [
    (['C714', 'R718', 'C713', 'R717', 'C701', 'C703', 'R704', 'R703', 'C709', 'R716', 'C622', 'C605', 'C606',
      'C718', 'R722', 'C715', 'R719', 'C601', 'C602', 'R602'], 'rows', (247.3, 80.9, 263.5, 94.3)),
    (['R705', 'R720', 'R721', 'R723', 'R603', 'C704', 'C716', 'C717', 'C719', 'C604', 'C1109', 'R1116', 'R1101',
      'C608', 'C620', 'C612'], 'cols', (200.0, 95.6, 216.0, 108.2)),
    (['R506', 'R505', 'R508', 'C509', 'C513', 'R501', 'C505'], 'rows', (189.1, 59.8, 203.4, 67.3)),
    (['C1103', 'R1102', 'C1102', 'R1103', 'C1101', 'R1104'], 'rows', (236.0, 119.4, 253.8, 125.1)),
    # power board: two of the voltage dividers next to J104 / J110 (the third has fixed spots)
    (['R101', 'R102', 'C101'], 'rows', (343.5, 77.8, 355.3, 86.0)),
    (['R103', 'R104', 'C102'], 'rows', (343.5, 104.6, 355.3, 109.4)),
]
# single parts with a fixed spot: above, below, left, right of the courtyard; 'up_' = upright text
FIXED = {'R109': 'up_above', 'C105': 'up_below', 'R110': 'up_below', 'C506': 'right', 'R601': 'up_right',
         'C1104': 'above', 'C516': 'below', 'R510': 'below', 'R511': 'up_below', 'C515': 'below', 'C503': 'up_left',
         'C609': 'below', 'C1108': 'up_left', 'D1105': 'right', 'D507': 'below',
         'R105': 'up_below', 'R106': 'up_above', 'C103': 'up_left',
         'R609': 'left', 'R606': 'left', 'R610': 'left', 'R607': 'left', 'R608': 'left', 'R611': 'left', 'C508': 'below', 'C510': 'above'}
FIXED_SHIFT = {'C506': (0.0, 0.3)}      # clear of the D502 outline


def ij(x, y):
    return int(round((x - X0) / G)), int(round((y - Y0) / G))


class Silk:
    def __init__(self, board, side='F'):
        self.b = board
        self.side = side
        self.block = np.zeros((NY, NX), bool)
        self._outline()
        self._parts()

    def box(self, x0, y0, x1, y1, grow=0.0):
        i0, j0 = ij(x0 - grow, y0 - grow)
        i1, j1 = ij(x1 + grow, y1 + grow)
        self.block[max(j0, 0):j1 + 1, max(i0, 0):i1 + 1] = True

    def _outline(self):
        ps = pcbnew.SHAPE_POLY_SET()
        self.b.GetBoardPolygonOutlines(ps, True)
        im = Image.new('1', (NX, NY), 0)
        d = ImageDraw.Draw(im)
        for k in range(ps.OutlineCount()):
            o = ps.Outline(k)
            d.polygon([((TM(o.CPoint(q).x) - X0) / G, (TM(o.CPoint(q).y) - Y0) / G) for q in range(o.PointCount())],
                      fill=1)
        inside = np.array(im, bool)
        from scipy import ndimage
        self.block |= ~ndimage.binary_erosion(inside, iterations=8)      # 0.8 mm to the board edge

    def _parts(self):
        bottom = self.side == 'B'
        silk, mask = (pcbnew.B_SilkS, pcbnew.B_Mask) if bottom else (pcbnew.F_SilkS, pcbnew.F_Mask)
        for f in self.b.GetFootprints():
            if f.IsFlipped() != bottom:
                # only the through holes of parts on the other side matter
                continue
            cy = f.GetCourtyard(pcbnew.B_CrtYd if bottom else pcbnew.F_CrtYd)
            if cy.OutlineCount():
                bb = cy.BBox()
                self.box(TM(bb.GetLeft()), TM(bb.GetTop()), TM(bb.GetRight()), TM(bb.GetBottom()))
            for g in f.GraphicalItems():
                if g.GetLayer() == silk:
                    bb = g.GetBoundingBox()
                    if TM(bb.GetWidth()) < 0.6 or TM(bb.GetHeight()) < 0.6 or g.GetClass() != 'PCB_SHAPE':
                        self.box(TM(bb.GetLeft()), TM(bb.GetTop()), TM(bb.GetRight()), TM(bb.GetBottom()), 0.1)
        for f in self.b.GetFootprints():
            for p in f.Pads():
                if p.IsOnLayer(mask) or p.GetDrillSize().x:
                    bb = p.GetBoundingBox()
                    self.box(TM(bb.GetLeft()), TM(bb.GetTop()), TM(bb.GetRight()), TM(bb.GetBottom()), 0.2)
        for d in self.b.GetDrawings():       # fixed texts already on this side
            if d.GetClass() == 'PCB_TEXT' and d.GetLayer() == silk:
                bb = d.GetBoundingBox()
                self.box(TM(bb.GetLeft()), TM(bb.GetTop()), TM(bb.GetRight()), TM(bb.GetBottom()), 0.1)

    def free(self, cx, cy, w, h):
        i0, j0 = ij(cx - w / 2, cy - h / 2)
        i1, j1 = ij(cx + w / 2, cy + h / 2)
        if i0 < 0 or j0 < 0 or i1 >= NX or j1 >= NY:
            return False
        return not self.block[j0:j1 + 1, i0:i1 + 1].any()

    def commit(self, pos, text, h):
        w, hh = len(text) * h * CHAR + 0.1, h * 1.25
        if pos[2]:
            w, hh = hh, w
        self.box(pos[0] - w / 2, pos[1] - hh / 2, pos[0] + w / 2, pos[1] + hh / 2, 0.1)

    def find(self, text, h, anchor, around, reach=6.0, prefer=None, commit=True):
        """around = bbox of the part (x0, y0, x1, y1); returns (x, y, angle) or None"""
        n = max(len(t) for t in text.split('\n'))
        w, hh = n * h * CHAR + 0.1, h * 1.25 * (text.count('\n') + 1)
        x0, y0, x1, y1 = around
        best = None
        for ang, (tw, th) in ((0, (w, hh)), (90, (hh, w))):
            step = 0.25
            for cx in np.arange(x0 - reach - tw / 2, x1 + reach + tw / 2, step):
                for cy in np.arange(y0 - reach - th / 2, y1 + reach + th / 2, step):
                    # distance of the text box to the part box
                    dx = max(x0 - (cx + tw / 2), (cx - tw / 2) - x1, 0)
                    dy = max(y0 - (cy + th / 2), (cy - th / 2) - y1, 0)
                    d = math.hypot(dx, dy)
                    if d > reach:
                        continue
                    cost = d + 0.15 * math.hypot(cx - anchor[0], cy - anchor[1]) + (0.4 if ang else 0.0)
                    if prefer:
                        cost += prefer(cx, cy)
                    if best is not None and cost >= best[0]:
                        continue
                    if self.free(cx, cy, tw + 0.2, th + 0.2):
                        best = (cost, cx, cy, ang, tw, th)
        if best is None:
            return None
        _, cx, cy, ang, tw, th = best
        if commit:
            self.box(cx - tw / 2, cy - th / 2, cx + tw / 2, cy + th / 2, 0.1)
        return float(cx), float(cy), ang


def set_text(t, x, y, ang, h, thick):
    t.SetTextSize(pcbnew.VECTOR2I(MM(h), MM(h)))
    t.SetTextThickness(MM(thick))
    t.SetTextAngleDegrees(ang)
    t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER)
    t.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)
    t.SetPosition(pcbnew.VECTOR2I(MM(float(x)), MM(float(y))))


def add_text(b, text, x, y, ang, h, thick, side='F'):
    t = pcbnew.PCB_TEXT(b)
    t.SetText(text)
    t.SetLayer(pcbnew.B_SilkS if side == 'B' else pcbnew.F_SilkS)
    set_text(t, x, y, ang, h, thick)
    if side == 'B':
        t.SetMirrored(True)          # readable when the board is turned over
    b.Add(t)


def part_numbers(b):
    """copy the schematic field Part# (LCSC number) into the footprints, hidden"""
    import os
    import re
    import subprocess
    import tempfile
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    with tempfile.TemporaryDirectory() as tmp:
        net = os.path.join(tmp, 'jacobi.net')
        subprocess.run(['kicad-cli', 'sch', 'export', 'netlist', '--format', 'kicadsexpr', '-o', net,
                        os.path.join(root, 'jacobi.kicad_sch')], check=True, capture_output=True)
        text = open(net).read()
    for comp in re.split(r'\(comp\s+(?=\(ref)', text)[1:]:
        ref = re.search(r'\(ref "([^"]+)"\)', comp).group(1)
        m = re.search(r'\(field\s*\(name "Part#"\)\s*(?:"([^"]*)")?', comp)
        f = b.FindFootprintByReference(ref)
        if m is None or f is None:
            continue
        f.SetField('Part#', m.group(1) or '')
        for fld in f.GetFields():
            if fld.GetName() == 'Part#':
                fld.SetVisible(False)
                fld.SetLayer(pcbnew.B_Fab if f.IsFlipped() else pcbnew.F_Fab)


def finish(B):
    b = B.b
    part_numbers(b)
    # old free texts go, the board marking comes back below
    for d in list(b.GetDrawings()):
        if d.GetClass() in ('PCB_TEXT', 'PCB_SHAPE') and d.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS):
            b.Delete(d)
    S = Silk(b)
    # board marking first so that it gets its place
    for text, x, y, h in (('UNIMOC JACOBI', 208.0, 132.6, 1.5), ('rev 0.3', 208.0, 134.9, 1.5),
                          ('UNIMOC JACOBI', 353.0, 60.3, 1.0), ('rev 0.3', 353.0, 61.8, 1.0)):
        w = len(text) * h * CHAR
        add_text(b, text, x, y, 0, h, 0.15 * h / 1.0 if h <= 1.0 else 0.25)
        S.box(x - w / 2, y - h * 0.65, x + w / 2, y + h * 0.65, 0.1)
    missing = []
    # the LED names right under the LEDs
    for r in LEDS:
        f = b.FindFootprintByReference(r)
        bb = f.GetCourtyard(pcbnew.F_CrtYd).BBox()
        x, y = TM(f.GetPosition().x), TM(bb.GetBottom()) + 0.9
        add_text(b, f.GetValue(), x, y, 0, 1.0, 0.15)
        S.commit((x, y, 0), f.GetValue(), 1.0)
    # designators: right at their part where that is unambiguous, the rest in a block per group
    done = power_labels(b, S)
    for r in LEDS:          # resistor name above the resistor, LED name upright beside the LED
        D = b.FindFootprintByReference(r)
        db = _crt(D)
        R = [p.GetParent() for p in D.Pads() if p.GetNumber() == '2'][0]
        R = [f for f in b.GetFootprints() if f.GetReference() != r and
             any(q.GetNetname() == [p for p in D.Pads() if p.GetNumber() == '2'][0].GetNetname() for q in f.Pads())][0]
        rb = _crt(R)
        _put(S, R, (rb[0] + rb[2]) / 2, rb[1] - 0.15 - 0.55, 0)
        # upright beside the LED, its lower end clear of the LED name below
        _put(S, D, db[2] + 0.3 + 0.55, min((db[1] + db[3]) / 2, db[3] + 0.9 - 0.55 - 0.2 - 2.35), 90)
        done |= {r, R.GetReference()}
    for refs, mode, area in SECTIONS:
        group = [(b.FindFootprintByReference(r), _crt(b.FindFootprintByReference(r))) for r in refs]
        missing += block(b, S, group, mode, area)
        done |= set(refs)
    for r, where in FIXED.items():
        f = b.FindFootprintByReference(r)
        x0, y0, x1, y1 = _crt(f)
        n = len(r) * CHAR + 0.1
        up = where.startswith('up_')
        w, hh = (1.1, n) if up else (n, 1.1)
        side = where[3:] if up else where
        x, y = {'above': ((x0 + x1) / 2, y0 - 0.15 - hh / 2), 'below': ((x0 + x1) / 2, y1 + 0.15 + hh / 2),
                'left': (x0 - 0.15 - w / 2, (y0 + y1) / 2), 'right': (x1 + 0.15 + w / 2, (y0 + y1) / 2)}[side]
        dx, dy = FIXED_SHIFT.get(r, (0.0, 0.0))
        _put(S, f, x + dx, y + dy, 90 if up else 0)
        done.add(r)
    # connector labels before the designators: they need the most room
    for r, label in LABEL.items():
        f = b.FindFootprintByReference(r)
        cy = f.GetCourtyard(pcbnew.F_CrtYd)
        bb = cy.BBox()
        around = (TM(bb.GetLeft()), TM(bb.GetTop()), TM(bb.GetRight()), TM(bb.GetBottom()))
        anchor = ((around[0] + around[2]) / 2, (around[1] + around[3]) / 2)
        # the designator goes with the function; where that does not fit, the function alone
        for text, h in ((f'{r} {label}', 1.2), (f'{r} {label}', 1.0), (label, 1.2), (label, 1.0)):
            pos = S.find(text, h, anchor, around, 6.0)
            if pos:
                add_text(b, text, pos[0], pos[1], pos[2], h, 0.15 * h)
                if text != label:
                    f.Reference().SetVisible(False)
                    done.add(r)
                break
        else:
            missing.append(r + ' label')
    parts = []
    for f in b.GetFootprints():
        for fld in f.GetFields():           # values, order numbers ...: not on the silkscreen
            if not fld.IsReference() and fld.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS):
                fld.SetVisible(False)
        r = f.GetReference()
        if f.IsFlipped() or r[0] in 'HN' or 'NetTie' in f.GetValue():
            f.Reference().SetVisible(not (r[0] in 'HN' or 'NetTie' in f.GetValue()))
            continue
        if r in done:
            continue
        cy = f.GetCourtyard(pcbnew.F_CrtYd)
        bb = cy.BBox() if cy.OutlineCount() else f.GetBoundingBox(False)
        parts.append((f, (TM(bb.GetLeft()), TM(bb.GetTop()), TM(bb.GetRight()), TM(bb.GetBottom()))))
    parts.sort(key=lambda p: (p[1][2] - p[1][0]) * (p[1][3] - p[1][1]))   # small parts first: fewest places
    boxes = [p[1] for p in parts]
    rest = []
    for f, box in parts:
        pos = attach(S, f.GetReference(), box, boxes)
        if pos is None and (f.GetReference()[0] in 'JPUXL' or (box[2] - box[0]) * (box[3] - box[1]) > 12):
            # connectors, ICs and big parts: nearest free spot
            pos = S.find(f.GetReference(), 1.0, ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2), box, 4.0)
        if pos is None:
            rest.append((f, box))
            continue
        ref = f.Reference()
        ref.SetVisible(True)
        ref.SetLayer(pcbnew.F_SilkS)
        set_text(ref, pos[0], pos[1], pos[2], 1.0, 0.15)
        ref.SetKeepUpright(True)
    for group in clusters(rest, 1.5):
        missing += legend(b, S, group)
    missing += bottom(b)
    print('silkscreen: no room for', missing)


def bottom(b):
    """pin names of the external connectors on the bottom side of the logic board"""
    S = Silk(b, 'B')
    missing = []
    for r, names in BOTTOM.items():
        f = b.FindFootprintByReference(r)
        inward = 1 if TM(f.GetPosition().x) < 222 else -1
        for p in f.Pads():
            k = int(p.GetNumber()) - 1
            px, py = TM(p.GetPosition().x), TM(p.GetPosition().y)
            name = names[k]
            pos = S.find(name, 1.0, (px, py), (px - 0.8, py - 0.8, px + 0.8, py + 0.8), 9.0, commit=False,
                         prefer=lambda cx, cy: 2.0 * abs(cy - py) + (3.0 if (cx - px) * inward < 0 else 0.0))
            if pos and abs(pos[1] - py) < 0.7 and pos[2] == 0:
                S.commit(pos, name, 1.0)
                add_text(b, name, pos[0], pos[1], 0, 1.0, 0.15, 'B')
            else:
                missing.append(f'{r}.{k + 1} bottom name')
    # SWD: 1.27 mm pitch, the names stand upright in a column above and below the pins
    f = b.FindFootprintByReference('P1101')
    rows = sorted({round(TM(p.GetPosition().y), 2) for p in f.Pads()})
    for p in f.Pads():
        name = SWD.get(p.GetNumber())
        if not name:
            continue
        px, py = TM(p.GetPosition().x), TM(p.GetPosition().y)
        n = len(name) * CHAR
        k = int(p.GetNumber())
        off = 0.75 + n / 2 + (n + 0.4 if (k - 1) // 2 % 2 else 0.0)   # every other column staggered
        y = py - off if py == rows[0] else py + off
        add_text(b, name, px, y, 90, 1.0, 0.15, 'B')
        S.box(px - 0.5, y - n / 2, px + 0.5, y + n / 2, 0.05)
    for r, text in BOTTOM_LABEL.items():
        f = b.FindFootprintByReference(r)
        bb = f.GetCourtyard(pcbnew.F_CrtYd).BBox()
        around = (TM(bb.GetLeft()), TM(bb.GetTop()), TM(bb.GetRight()), TM(bb.GetBottom()))
        anchor = ((around[0] + around[2]) / 2, (around[1] + around[3]) / 2)
        for h in (1.2, 1.0):
            pos = S.find(text, h, anchor, around, 6.0)
            if pos:
                add_text(b, text, pos[0], pos[1], pos[2], h, 0.15 * h, 'B')
                break
        else:
            missing.append(r + ' bottom label')
    return missing


def _crt(f):
    bb = f.GetCourtyard(pcbnew.F_CrtYd).BBox()
    return TM(bb.GetLeft()), TM(bb.GetTop()), TM(bb.GetRight()), TM(bb.GetBottom())


def _put(S, f, x, y, ang, h=1.0):
    ref = f.Reference()
    ref.SetVisible(True)
    ref.SetLayer(pcbnew.F_SilkS)
    set_text(ref, x, y, ang, h, 0.15)
    ref.SetKeepUpright(True)
    w, hh = len(f.GetReference()) * h * CHAR + 0.1, h * 1.25
    if ang:
        w, hh = hh, w
    S.box(x - w / 2, y - hh / 2, x + w / 2, y + hh / 2, 0.05)


def power_labels(b, S):
    """the gate network of every FET is labelled the same way: the two gate resistors in line with
    their row (the net ties have no mask opening and no designator), the FET upright on the outer
    side of its column. In the driver block the driver is named upright on its left, the bootstrap
    capacitor upright below it."""
    done = set()
    fp = b.FindFootprintByReference
    for n in (2, 3, 4):
        # FET: (gate resistor upper row, lower row, side of the labels, column)
        for q, ru, rl, side in ((2, 12, 5, 'right'), (1, 11, 3, 'right'), (4, 7, 14, 'left'), (3, 13, 9, 'right')):
            Q = fp(f'Q{n}{q:02d}')
            qb = _crt(Q)
            col1 = TM(Q.GetPosition().x) < 330
            qx = qb[0] - 0.75 if col1 else qb[2] + 0.75
            _put(S, Q, qx, (qb[1] + qb[3]) / 2, 90)
            done.add(Q.GetReference())
            for k in (ru, rl):
                R = fp(f'R{n}{k:02d}')
                rb = _crt(R)
                w = len(R.GetReference()) * CHAR + 0.1
                y = TM(R.GetPosition().y)
                if side == 'right':
                    x = rb[2] + 0.2 + w / 2
                elif side == 'left':
                    x = rb[0] - 0.2 - w / 2
                _put(S, R, x, y, 0)
                done.add(R.GetReference())
        U, C = fp(f'U{n}01'), fp(f'C{n}03')
        ub, cb = _crt(U), _crt(C)
        if n == 2:
            # next to the mounting hole: diode name upright beside the diode, driver name below the driver
            D = fp('D201')
            _put(S, D, ub[0] - 0.45, 62.3, 90)
            _put(S, U, ub[2] - 0.9 - 1.85, ub[3] + 0.73, 0)
            done.add('D201')
        else:
            _put(S, U, ub[0] - 0.75, (ub[1] + ub[3]) / 2, 90)
        _put(S, C, (cb[0] + cb[2]) / 2, cb[3] + 0.2 + 2.0, 90)
        done |= {U.GetReference(), C.GetReference()}
    return done


def _box_dist(x, y, box):
    return math.hypot(max(box[0] - x, 0, x - box[2]), max(box[1] - y, 0, y - box[3]))


def _rect_dist(a, b):
    return math.hypot(max(a[0] - b[2], b[0] - a[2], 0), max(a[1] - b[3], b[1] - a[3], 0))


def attach(S, text, box, boxes, h=1.0):
    """designator right next to its part, on one of its sides, unambiguous: in line with the part
    and touching no other part closer than its own, or clearly nearer to its own part than to any other"""
    x0, y0, x1, y1 = box
    w, th = len(text) * h * CHAR + 0.1, h * 1.1
    near = [o for o in boxes if o is not box and _box_dist((x0 + x1) / 2, (y0 + y1) / 2, o) < 10]
    cands = []
    for gap in (0.1, 0.2, 0.35, 0.5):
        for off in np.arange(-3.0, 3.01, 0.25):
            if abs(off) <= max(0.0, (x1 - x0) / 2):            # above and below, horizontal
                cx = (x0 + x1) / 2 + off
                for cy in (y0 - gap - th / 2, y1 + gap + th / 2):
                    cands.append((gap + 0.3 * abs(off), cx, cy, 0, w, th, gap, abs(off)))
            if abs(off) <= max(0.0, (y1 - y0) / 2):            # left and right, horizontal
                cy = (y0 + y1) / 2 + off
                for cx in (x0 - gap - w / 2, x1 + gap + w / 2):
                    cands.append((gap + 0.3 * abs(off) + 0.1, cx, cy, 0, w, th, gap, abs(off)))
            if abs(off) <= max(0.0, (y1 - y0 - w) / 2 + 0.3):  # left and right, upright
                cy = (y0 + y1) / 2 + off
                for cx in (x0 - gap - th / 2, x1 + gap + th / 2):
                    cands.append((gap + 0.3 * abs(off) + 0.5, cx, cy, 90, th, w, gap, abs(off)))
    cands.sort(key=lambda c: c[0])
    for cost, cx, cy, ang, tw, hh, gap, off in cands:
        if not S.free(cx, cy, tw + 0.2, hh + 0.2):
            continue
        t = (cx - tw / 2, cy - hh / 2, cx + tw / 2, cy + hh / 2)
        if off <= 0.25:
            ok = all(_rect_dist(t, o) >= gap + 0.05 for o in near)
        else:
            own = _box_dist(cx, cy, box)
            ok = all(_rect_dist(t, o) >= gap + 0.4 and _box_dist(cx, cy, o) >= own + 0.2 for o in near)
        if not ok:
            continue
        S.box(*t, 0.1)
        return float(cx), float(cy), ang
    return None


def block(b, S, group, mode, area, h=1.0, pitch=1.4):
    """framed block of the group's designators inside area, as close to the group as possible"""
    cx = [(bx[0] + bx[2]) / 2 for _, bx in group]
    cy = [(bx[1] + bx[3]) / 2 for _, bx in group]
    if mode == 'rows':
        idx, n = _lines(cy)
        lines = [' '.join(f.GetReference() for (f, _), x, k in sorted(zip(group, cx, idx), key=lambda t: t[1]) if k == i)
                 for i in range(n)]
    else:
        idx, n = _lines(cx)
        # upright text reads upwards: the lowest part first
        lines = [' '.join(f.GetReference() for (f, _), y, k in sorted(zip(group, cy, idx), key=lambda t: -t[1]) if k == i)
                 for i in range(n)]
    long = max(len(t) for t in lines) * h * CHAR + 0.1
    W, H = (long + 0.9, n * pitch + 0.45) if mode == 'rows' else (n * pitch + 0.45, long + 0.9)
    gx0, gy0 = min(bx[0] for _, bx in group), min(bx[1] for _, bx in group)
    gx1, gy1 = max(bx[2] for _, bx in group), max(bx[3] for _, bx in group)
    best = None
    for px in np.arange(area[0] + W / 2, area[2] - W / 2 + 0.01, 0.2):
        for py in np.arange(area[1] + H / 2, area[3] - H / 2 + 0.01, 0.2):
            d = math.hypot(max(gx0 - (px + W / 2), (px - W / 2) - gx1, 0), max(gy0 - (py + H / 2), (py - H / 2) - gy1, 0))
            if (best is None or d < best[0]) and S.free(px, py, W + 0.2, H + 0.2):
                best = (d, px, py)
    if best is None:
        for f, _ in group:
            f.Reference().SetVisible(False)
        return [f.GetReference() for f, _ in group]
    _, px, py = best
    x0, y0 = px - W / 2, py - H / 2
    S.box(x0, y0, x0 + W, y0 + H, 0.1)
    for f, _ in group:
        f.Reference().SetVisible(False)
    for i, t in enumerate(lines):
        w = len(t) * h * CHAR
        if mode == 'rows':
            add_text(b, t, x0 + 0.45 + w / 2, y0 + 0.3 + (i + 0.5) * pitch, 0, h, 0.15)
        else:
            add_text(b, t, x0 + 0.3 + (i + 0.5) * pitch, y0 + H - 0.45 - w / 2, 90, h, 0.15)
    frame = pcbnew.PCB_SHAPE(b)
    frame.SetShape(pcbnew.SHAPE_T_RECT)
    frame.SetLayer(pcbnew.F_SilkS)
    frame.SetWidth(MM(0.15))
    frame.SetFilled(False)
    frame.SetStart(pcbnew.VECTOR2I(MM(float(x0)), MM(float(y0))))
    frame.SetEnd(pcbnew.VECTOR2I(MM(float(x0 + W)), MM(float(y0 + H))))
    b.Add(frame)
    return []


def clusters(items, dist=2.5):
    """group parts whose courtyards are closer than dist"""
    n = len(items)
    up = list(range(n))

    def root(i):
        while up[i] != i:
            up[i] = up[up[i]]
            i = up[i]
        return i
    for i in range(n):
        for j in range(i + 1, n):
            a, b = items[i][1], items[j][1]
            if max(a[0] - b[2], b[0] - a[2], a[1] - b[3], b[1] - a[3]) < dist:
                up[root(i)] = root(j)
    groups = {}
    for i in range(n):
        groups.setdefault(root(i), []).append(items[i])
    return list(groups.values())


def _lines(vals, tol=0.8):
    """index of the row (or column) of each value"""
    order = sorted(range(len(vals)), key=lambda i: vals[i])
    idx, k, last = [0] * len(vals), -1, None
    for i in order:
        if last is None or vals[i] - last > tol:
            k += 1
        idx[i] = k
        last = vals[i]
    return idx, k + 1


def legend(b, S, group, h=1.0):
    """a framed block of designators next to the group, in the same arrangement as the parts"""
    refs = [f.GetReference() for f, _ in group]
    cx = [(bx[0] + bx[2]) / 2 for _, bx in group]
    cy = [(bx[1] + bx[3]) / 2 for _, bx in group]
    col, nc = _lines(cx)
    row, nr = _lines(cy)
    cw = [0.0] * nc
    for r, c in zip(refs, col):
        cw[c] = max(cw[c], len(r) * h * CHAR + 0.5)
    rh = h * 1.4
    W, H = sum(cw) + 0.4, nr * rh + 0.4
    around = (min(bx[0] for _, bx in group), min(bx[1] for _, bx in group),
              max(bx[2] for _, bx in group), max(bx[3] for _, bx in group))
    best = None
    for reach in ((1.0, 2.5, 4.0) if len(group) > 1 else ()):
        x0, y0, x1, y1 = around
        for px in np.arange(x0 - reach - W / 2, x1 + reach + W / 2, 0.25):
            for py in np.arange(y0 - reach - H / 2, y1 + reach + H / 2, 0.25):
                dx = max(x0 - (px + W / 2), (px - W / 2) - x1, 0)
                dy = max(y0 - (py + H / 2), (py - H / 2) - y1, 0)
                d = math.hypot(dx, dy)
                if d > reach or (best and d >= best[0]):
                    continue
                if S.free(px, py, W + 0.3, H + 0.3):
                    best = (d, px, py)
        if best:
            break
    if best is None or len(group) == 1:
        if len(group) == 1:
            f, bx = group[0]
            pos = S.find(refs[0], h, ((bx[0] + bx[2]) / 2, (bx[1] + bx[3]) / 2), bx, 5.0)
            if pos is None:
                f.Reference().SetVisible(False)
                return refs
            set_text(f.Reference(), pos[0], pos[1], pos[2], h, 0.15)
            f.Reference().SetVisible(True)
            return []
        # too big for the free spots around it: split along its longer side and try the halves
        horiz = (around[2] - around[0]) >= (around[3] - around[1])
        key = (lambda g: g[1][0] + g[1][2]) if horiz else (lambda g: g[1][1] + g[1][3])
        g = sorted(group, key=key)
        k = len(g) // 2
        return legend(b, S, g[:k], h) + legend(b, S, g[k:], h)
    _, px, py = best
    S.box(px - W / 2, py - H / 2, px + W / 2, py + H / 2, 0.1)
    left, top = px - W / 2 + 0.2, py - H / 2 + 0.2
    xs = [left + sum(cw[:c]) + cw[c] / 2 for c in range(nc)]
    for (f, _), c, r in zip(group, col, row):
        f.Reference().SetVisible(False)
        add_text(b, f.GetReference(), xs[c], top + (r + 0.5) * rh, 0, h, 0.15)
    frame = pcbnew.PCB_SHAPE(b)
    frame.SetShape(pcbnew.SHAPE_T_RECT)
    frame.SetLayer(pcbnew.F_SilkS)
    frame.SetWidth(MM(0.15))
    frame.SetFilled(False)
    frame.SetStart(pcbnew.VECTOR2I(MM(float(px - W / 2)), MM(float(py - H / 2))))
    frame.SetEnd(pcbnew.VECTOR2I(MM(float(px + W / 2)), MM(float(py + H / 2))))
    b.Add(frame)
    return []
