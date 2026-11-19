"""Small helper layer over pcbnew for scripted layout (mm units)."""
import pcbnew

MM = pcbnew.FromMM
L = {'F': pcbnew.F_Cu, 'I1': pcbnew.In1_Cu, 'I2': pcbnew.In2_Cu, 'B': pcbnew.B_Cu}


class Board:
    def __init__(self, path):
        self.b = pcbnew.LoadBoard(path)
        self.nets = self.b.GetNetsByName()

    def net(self, name):
        n = self.b.FindNet(name)
        if n is None:
            raise KeyError(name)
        return n

    def fp(self, ref):
        f = self.b.FindFootprintByReference(ref)
        if f is None:
            raise KeyError(ref)
        return f

    def place(self, ref, x, y, rot=None, lock=None):
        f = self.fp(ref)
        f.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
        if rot is not None:
            f.SetOrientationDegrees(rot)
        if lock is not None:
            f.SetLocked(lock)
        return f

    def pad(self, ref, num):
        """(x, y, netname) of the first pad with this number."""
        for p in self.fp(ref).Pads():
            if p.GetNumber() == str(num):
                return pcbnew.ToMM(p.GetPosition().x), pcbnew.ToMM(p.GetPosition().y), p.GetNetname()
        raise KeyError((ref, num))

    def track(self, net, layer, pts, w=0.25, lock=True, chamfer=0.4):
        n = self.net(net)
        pts = chamfered(pts, chamfer) if chamfer else pts
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            if abs(x1 - x2) < 1e-6 and abs(y1 - y2) < 1e-6:
                continue
            t = pcbnew.PCB_TRACK(self.b)
            t.SetStart(pcbnew.VECTOR2I(MM(x1), MM(y1)))
            t.SetEnd(pcbnew.VECTOR2I(MM(x2), MM(y2)))
            t.SetWidth(MM(w))
            t.SetLayer(L[layer])
            t.SetNet(n)
            t.SetLocked(lock)
            self.b.Add(t)

    def via(self, net, x, y, d=0.6, drill=0.3, lock=True):
        v = pcbnew.PCB_VIA(self.b)
        v.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
        v.SetViaType(pcbnew.VIATYPE_THROUGH)
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        v.SetWidth(pcbnew.F_Cu, MM(d))
        v.SetDrill(MM(drill))
        v.SetNet(self.net(net))
        v.SetLocked(lock)
        self.b.Add(v)

    def vias(self, net, pts, d=0.8, drill=0.4):
        for x, y in pts:
            self.via(net, x, y, d, drill)

    def zone(self, net, layers, pts, prio=0, clr=0.3, minw=0.25, name='', solid=True, island='area'):
        z = pcbnew.ZONE(self.b)
        ls = pcbnew.LSET()
        for l in layers:
            ls.AddLayer(L[l])
        z.SetLayerSet(ls)
        z.SetNet(self.net(net))
        ol = z.Outline()
        ol.NewOutline()
        for x, y in pts:
            ol.Append(MM(x), MM(y))
        z.SetAssignedPriority(prio)
        z.SetLocalClearance(MM(clr))
        z.SetMinThickness(MM(minw))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL if solid else pcbnew.ZONE_CONNECTION_THERMAL)
        z.SetThermalReliefGap(MM(0.3))
        z.SetThermalReliefSpokeWidth(MM(0.4))
        if island == 'never':
            z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_NEVER)
        elif island == 'always':
            z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        else:
            z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_AREA)
            z.SetMinIslandArea(MM(1.0) * MM(1.0))
        z.SetZoneName(name or net)
        self.b.Add(z)
        return z

    def keepout(self, layers, pts, tracks=True, vias=True, copper=False, name='keepout'):
        z = pcbnew.ZONE(self.b)
        ls = pcbnew.LSET()
        for l in layers:
            ls.AddLayer(L[l])
        z.SetLayerSet(ls)
        z.SetIsRuleArea(True)
        z.SetDoNotAllowTracks(tracks)
        z.SetDoNotAllowVias(vias)
        z.SetDoNotAllowZoneFills(copper)
        z.SetDoNotAllowPads(False)
        z.SetDoNotAllowFootprints(False)
        ol = z.Outline()
        ol.NewOutline()
        for x, y in pts:
            ol.Append(MM(x), MM(y))
        z.SetZoneName(name)
        self.b.Add(z)
        return z

    def fill(self):
        pcbnew.ZONE_FILLER(self.b).Fill(self.b.Zones())

    def save(self, path):
        pcbnew.SaveBoard(path, self.b)


def rect(x1, y1, x2, y2):
    return [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]


# ---------------------------------------------------------------- geometry
import math


def _seg_pt(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - x1 - t * dx, py - y1 - t * dy)


class Checker:
    """Conservative clearance test for new through vias (all layers at once)."""

    def __init__(self, board, xmin=None, xmax=None):
        b = board.b
        tm = pcbnew.ToMM
        self.segs, self.circ, self.rects = [], [], []
        for t in b.GetTracks():
            if t.GetClass() == 'PCB_VIA':
                self.circ.append((tm(t.GetPosition().x), tm(t.GetPosition().y), tm(t.GetWidth(pcbnew.F_Cu)) / 2,
                                  tm(t.GetDrill()) / 2, t.GetNetname()))
            else:
                self.segs.append((tm(t.GetStart().x), tm(t.GetStart().y), tm(t.GetEnd().x), tm(t.GetEnd().y),
                                  tm(t.GetWidth()) / 2, t.GetNetname()))
        for f in b.GetFootprints():
            for p in f.Pads():
                bb = p.GetBoundingBox()
                dr = tm(p.GetDrillSize().x) / 2
                self.rects.append((tm(bb.GetLeft()), tm(bb.GetTop()), tm(bb.GetRight()), tm(bb.GetBottom()),
                                   dr, p.GetNetname(), p.GetShape(pcbnew.F_Cu) == pcbnew.PAD_SHAPE_CIRCLE))

    def ok(self, x, y, r, net, clr=0.25, drill=0.2, hole=0.3, same_pad_gap=None):
        for x1, y1, x2, y2, hw, n in self.segs:
            if n != net and _seg_pt(x, y, x1, y1, x2, y2) < r + hw + clr:
                return False
        for cx, cy, cr, cd, n in self.circ:
            d = math.hypot(x - cx, y - cy)
            if n != net and d < r + cr + clr:
                return False
            if d < drill + cd + hole:
                return False
        for l, t, rr, bt, dr, n, circ in self.rects:
            if circ:
                cx, cy, cr = (l + rr) / 2, (t + bt) / 2, (rr - l) / 2
                d = math.hypot(x - cx, y - cy) - cr
            else:
                dx = max(l - x, 0, x - rr)
                dy = max(t - y, 0, y - bt)
                d = math.hypot(dx, dy)
            if n != net:
                if d < r + clr:
                    return False
            else:
                if dr > 0 and d < drill + hole - 0.0 and not circ:
                    return False
                if dr > 0 and circ and d + cr < drill + dr + hole:
                    return False
                if same_pad_gap is not None and dr == 0 and d < r + same_pad_gap:
                    return False
        return True

    def add_via(self, x, y, r, drill, net):
        self.circ.append((x, y, r, drill, net))


def grid(x0, x1, dx, y0, y1, dy):
    pts = []
    nx = int(round((x1 - x0) / dx)) if dx else 0
    ny = int(round((y1 - y0) / dy)) if dy else 0
    for i in range(nx + 1):
        for j in range(ny + 1):
            pts.append((x0 + i * dx, y0 + j * dy))
    return pts


def chamfered(pts, c):
    """replace every corner sharper than 45 degrees by a 45 degree chamfer of leg c (shortened to fit)"""
    import math
    out = [pts[0]]
    for a, b, d in zip(pts, pts[1:], pts[2:]):
        v1 = (b[0] - a[0], b[1] - a[1])
        v2 = (d[0] - b[0], d[1] - b[1])
        l1, l2 = math.hypot(*v1), math.hypot(*v2)
        if l1 < 1e-6 or l2 < 1e-6:
            out.append(b)
            continue
        cos = (v1[0] * v2[0] + v1[1] * v2[1]) / (l1 * l2)
        if cos > 0.5:              # 45 degree bend or less: keep
            out.append(b)
            continue
        k = min(c, 0.45 * l1, 0.45 * l2)
        out.append((b[0] - v1[0] / l1 * k, b[1] - v1[1] / l1 * k))
        out.append((b[0] + v2[0] / l2 * k, b[1] + v2[1] / l2 * k))
    out.append(pts[-1])
    return out
