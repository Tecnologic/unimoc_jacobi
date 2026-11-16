"""Silkscreen: reference designators, connector labels, board marking.

Every designator is put on a free spot next to its part: not on a pad, not
under another part, not on other silkscreen and inside the board. Values and
other footprint texts stay on the fabrication layer only.
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
PINS = {    # connector -> pin names
    'J501': ['BAT', 'VIN', 'EN+', 'EN-'], 'J1103': ['SH', 'L', 'H', 'NC'], 'J1104': ['SH', 'L', 'H', 'NC'],
    'J601': ['GND', 'BRK', 'ACC', '3V3'], 'J701': ['GND', 'NTC'], 'J1101': ['GND', 'A', 'B', 'C', '5V'],
}


def ij(x, y):
    return int(round((x - X0) / G)), int(round((y - Y0) / G))


class Silk:
    def __init__(self, board):
        self.b = board
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
        for f in self.b.GetFootprints():
            if f.IsFlipped():
                # only the through holes of bottom-side parts matter on the top silkscreen
                continue
            cy = f.GetCourtyard(pcbnew.F_CrtYd)
            if cy.OutlineCount():
                bb = cy.BBox()
                self.box(TM(bb.GetLeft()), TM(bb.GetTop()), TM(bb.GetRight()), TM(bb.GetBottom()))
            for g in f.GraphicalItems():
                if g.GetLayer() == pcbnew.F_SilkS:
                    bb = g.GetBoundingBox()
                    if TM(bb.GetWidth()) < 0.6 or TM(bb.GetHeight()) < 0.6 or g.GetClass() != 'PCB_SHAPE':
                        self.box(TM(bb.GetLeft()), TM(bb.GetTop()), TM(bb.GetRight()), TM(bb.GetBottom()), 0.1)
        for f in self.b.GetFootprints():
            for p in f.Pads():
                if p.IsOnLayer(pcbnew.F_Mask) or p.GetDrillSize().x:
                    bb = p.GetBoundingBox()
                    self.box(TM(bb.GetLeft()), TM(bb.GetTop()), TM(bb.GetRight()), TM(bb.GetBottom()), 0.2)

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


def add_text(b, text, x, y, ang, h, thick):
    t = pcbnew.PCB_TEXT(b)
    t.SetText(text)
    t.SetLayer(pcbnew.F_SilkS)
    set_text(t, x, y, ang, h, thick)
    b.Add(t)


def finish(B):
    b = B.b
    # old free texts go, the board marking comes back below
    for d in list(b.GetDrawings()):
        if d.GetClass() == 'PCB_TEXT' and d.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS):
            b.Delete(d)
    S = Silk(b)
    # board marking first so that it gets its place
    for text, x, y, h in (('UNIMOC JACOBI rev 0.3', 219.25, 134.4, 1.5), ('UNIMOC JACOBI', 353.0, 60.3, 1.0),
                          ('rev 0.3', 353.0, 61.8, 1.0)):
        w = len(text) * h * CHAR
        add_text(b, text, x, y, 0, h, 0.15 * h / 1.0 if h <= 1.0 else 0.25)
        S.box(x - w / 2, y - h * 0.65, x + w / 2, y + h * 0.65, 0.1)
    missing = []
    # pin names first: they only make sense right next to their pin
    for r, names in PINS.items():
        f = b.FindFootprintByReference(r)
        fx = TM(f.GetPosition().x)
        inward = 1 if fx < 222 else -1          # the pin names stand on the board side of the pins
        for p in f.Pads():
            k = int(p.GetNumber()) - 1
            px, py = TM(p.GetPosition().x), TM(p.GetPosition().y)
            name = names[k]
            pos = S.find(name, 1.0, (px, py), (px - 0.8, py - 0.8, px + 0.8, py + 0.8), 5.5, commit=False,
                         prefer=lambda cx, cy: 2.0 * abs(cy - py) + (3.0 if (cx - px) * inward < 0 else 0.0))
            if pos and abs(pos[1] - py) < 0.7 and pos[2] == 0:
                S.commit(pos, name, 1.0)
                add_text(b, name, pos[0], pos[1], 0, 1.0, 0.15)
            else:
                missing.append(f'{r}.{k + 1} name')
    fps = sorted(b.GetFootprints(), key=lambda f: -f.GetBoundingBox(False).GetWidth() * f.GetBoundingBox(False).GetHeight())
    for f in fps:
        ref = f.Reference()
        val = f.Value()
        for fld in f.GetFields():           # values, order numbers ...: not on the silkscreen
            if not fld.IsReference() and fld.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS):
                fld.SetVisible(False)
        r = f.GetReference()
        if f.IsFlipped() or r[0] in 'HN':
            ref.SetVisible(not r[0] in 'HN')
            continue
        cy = f.GetCourtyard(pcbnew.F_CrtYd)
        bb = cy.BBox() if cy.OutlineCount() else f.GetBoundingBox(False)
        around = (TM(bb.GetLeft()), TM(bb.GetTop()), TM(bb.GetRight()), TM(bb.GetBottom()))
        anchor = (TM(f.GetPosition().x), TM(f.GetPosition().y))
        pos = None
        for h, reach in ((1.0, 1.5), (1.0, 3.5), (1.0, 9.0)):
            pos = S.find(r, h, anchor, around, reach)
            if pos:
                break
        if pos is None:
            ref.SetVisible(False)
            missing.append(r)
            continue
        ref.SetVisible(True)
        ref.SetLayer(pcbnew.F_SilkS)
        set_text(ref, pos[0], pos[1], pos[2], h, 0.15)
        ref.SetKeepUpright(True)
    # connector labels and pin names
    for r, text in LABEL.items():
        f = b.FindFootprintByReference(r)
        cy = f.GetCourtyard(pcbnew.F_CrtYd)
        bb = cy.BBox()
        around = (TM(bb.GetLeft()), TM(bb.GetTop()), TM(bb.GetRight()), TM(bb.GetBottom()))
        anchor = ((around[0] + around[2]) / 2, (around[1] + around[3]) / 2)
        for h in (1.2, 1.0):
            pos = S.find(text, h, anchor, around, 6.0)
            if pos:
                add_text(b, text, pos[0], pos[1], pos[2], h, 0.15 * h)
                break
        else:
            missing.append(r + ' label')
    print('silkscreen: no room for', missing)
