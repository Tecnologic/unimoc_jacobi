"""Grid maze router for the small-signal nets (own code, works on a kl.Board).

Grid 0.1 mm, 8 directions, through vias, two (or more) routing layers. Copper of
every layer is rasterised with its net; a cell is usable for a net when all
foreign copper is further away than clearance + half the track width.
"""
import heapq
import math

import numpy as np
import pcbnew
from PIL import Image, ImageDraw
from scipy import ndimage

from kl import L

G = 0.1
TM = pcbnew.ToMM
ALL = ['F', 'I1', 'I2', 'B']
MARGIN = 0.06
SQ2 = math.sqrt(2.0)


class Router:
    def __init__(self, board, region, layers=('F', 'B'), edge=0.5, via=(0.6, 0.3)):
        self.B = board
        self.b = board.b
        self.x0, self.y0, self.x1, self.y1 = region
        self.nx = int(round((self.x1 - self.x0) / G)) + 1
        self.ny = int(round((self.y1 - self.y0) / G)) + 1
        self.layers = list(layers)
        self.via_d, self.via_drill = via
        self.ids = {}
        self.cop = {l: np.zeros((self.ny, self.nx), np.int32) for l in ALL}
        self.hole = np.zeros((self.ny, self.nx), bool)       # drilled area (any net)
        self.smd = np.zeros((self.ny, self.nx), bool)        # SMD pad area (no via in pad)
        self.noroute = {l: np.zeros((self.ny, self.nx), bool) for l in ALL}
        self.novia = np.zeros((self.ny, self.nx), bool)
        self.failed = []
        self._outline(edge)
        self._load()

    # ------------------------------------------------------------ raster helpers
    def nid(self, name):
        if name not in self.ids:
            self.ids[name] = len(self.ids) + 1
        return self.ids[name]

    def ij(self, x, y):
        return int(round((x - self.x0) / G)), int(round((y - self.y0) / G))

    def xy(self, i, j):
        return round(self.x0 + i * G, 4), round(self.y0 + j * G, 4)

    def _clip(self, i0, j0, i1, j1):
        return max(i0, 0), max(j0, 0), min(i1, self.nx - 1), min(j1, self.ny - 1)

    def _put(self, arr, mask_slice, sub, n):
        """write net n into arr[mask_slice] where sub is True; clashes become -1"""
        a = arr[mask_slice]
        clash = sub & (a != 0) & (a != n)
        a[sub & (a == 0)] = n
        a[clash] = -1

    def rect(self, layer, x0, y0, x1, y1, n):
        i0, j0 = self.ij(x0 + G / 2 - 1e-6, y0 + G / 2 - 1e-6)
        i1, j1 = self.ij(x1 - G / 2 + 1e-6, y1 - G / 2 + 1e-6)
        i0, j0, i1, j1 = self._clip(i0, j0, i1, j1)
        if i1 < i0 or j1 < j0:
            return None
        sl = (slice(j0, j1 + 1), slice(i0, i1 + 1))
        if layer is not None:
            self._put(self.cop[layer], sl, np.ones((j1 - j0 + 1, i1 - i0 + 1), bool), n)
        return sl

    def disk_mask(self, x, y, r):
        i0, j0 = self.ij(x - r - G, y - r - G)
        i1, j1 = self.ij(x + r + G, y + r + G)
        i0, j0, i1, j1 = self._clip(i0, j0, i1, j1)
        if i1 < i0 or j1 < j0:
            return None, None
        jj, ii = np.mgrid[j0:j1 + 1, i0:i1 + 1]
        m = (self.x0 + ii * G - x) ** 2 + (self.y0 + jj * G - y) ** 2 <= r * r + 1e-9
        return (slice(j0, j1 + 1), slice(i0, i1 + 1)), m

    def disk(self, layer, x, y, r, n):
        sl, m = self.disk_mask(x, y, r)
        if sl is not None:
            self._put(self.cop[layer], sl, m, n)

    def seg(self, layer, xa, ya, xb, yb, hw, n):
        i0, j0 = self.ij(min(xa, xb) - hw - G, min(ya, yb) - hw - G)
        i1, j1 = self.ij(max(xa, xb) + hw + G, max(ya, yb) + hw + G)
        i0, j0, i1, j1 = self._clip(i0, j0, i1, j1)
        if i1 < i0 or j1 < j0:
            return
        jj, ii = np.mgrid[j0:j1 + 1, i0:i1 + 1]
        px, py = self.x0 + ii * G, self.y0 + jj * G
        dx, dy = xb - xa, yb - ya
        l2 = dx * dx + dy * dy
        t = np.zeros_like(px) if l2 == 0 else np.clip(((px - xa) * dx + (py - ya) * dy) / l2, 0, 1)
        m = (px - xa - t * dx) ** 2 + (py - ya - t * dy) ** 2 <= hw * hw + 1e-9
        self._put(self.cop[layer], (slice(j0, j1 + 1), slice(i0, i1 + 1)), m, n)

    def poly_mask(self, pts):
        im = Image.new('1', (self.nx, self.ny), 0)
        ImageDraw.Draw(im).polygon([((x - self.x0) / G, (y - self.y0) / G) for x, y in pts], fill=1)
        return np.array(im, bool)

    def keepout(self, pts, layers=ALL, vias=True, tracks=True):
        m = self.poly_mask(pts)
        if tracks:
            for l in layers:
                self.noroute[l] |= m
        if vias:
            self.novia |= m

    # ------------------------------------------------------------ board -> raster
    def _outline(self, edge):
        ps = pcbnew.SHAPE_POLY_SET()
        self.b.GetBoardPolygonOutlines(ps, True)
        inside = np.zeros((self.ny, self.nx), bool)
        for k in range(ps.OutlineCount()):
            o = ps.Outline(k)
            pts = [(TM(o.CPoint(q).x), TM(o.CPoint(q).y)) for q in range(o.PointCount())]
            inside |= self.poly_mask(pts)
        self.inside = inside
        d = ndimage.distance_transform_edt(inside) * G
        self.edge_dist = d

    def _load(self):
        for f in self.b.GetFootprints():
            for p in f.Pads():
                bb = p.GetBoundingBox()
                x0, y0, x1, y1 = TM(bb.GetLeft()), TM(bb.GetTop()), TM(bb.GetRight()), TM(bb.GetBottom())
                if x1 < self.x0 or x0 > self.x1 or y1 < self.y0 or y0 > self.y1:
                    continue
                name = p.GetNetname() or f'~{f.GetReference()}-{p.GetNumber()}'
                n = self.nid(name)
                cx, cy = TM(p.GetPosition().x), TM(p.GetPosition().y)
                circ = p.GetShape(pcbnew.F_Cu) == pcbnew.PAD_SHAPE_CIRCLE
                for l in ALL:
                    if not p.IsOnLayer(L[l]):
                        continue
                    if circ:
                        self.disk(l, cx, cy, (x1 - x0) / 2, n)
                    else:
                        self.rect(l, x0, y0, x1, y1, n)
                dr = TM(p.GetDrillSize().x) / 2
                if dr > 0:
                    sl, m = self.disk_mask(cx, cy, dr)
                    if sl is not None:
                        self.hole[sl] |= m
                    if p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                        for l in ALL:
                            self.disk(l, cx, cy, dr, -1)
                elif p.IsOnLayer(pcbnew.F_Cu) or p.IsOnLayer(pcbnew.B_Cu):
                    sl = self.rect(None, x0 - 0.1, y0 - 0.1, x1 + 0.1, y1 + 0.1, 0)
                    if sl is not None:
                        self.smd[sl] = True
        for t in self.b.GetTracks():
            n = self.nid(t.GetNetname())
            if t.GetClass() == 'PCB_VIA':
                x, y = TM(t.GetPosition().x), TM(t.GetPosition().y)
                self.add_via(x, y, TM(t.GetWidth(pcbnew.F_Cu)) / 2, TM(t.GetDrill()) / 2, n)
            else:
                l = [k for k, v in L.items() if v == t.GetLayer()][0]
                self.seg(l, TM(t.GetStart().x), TM(t.GetStart().y), TM(t.GetEnd().x), TM(t.GetEnd().y),
                         TM(t.GetWidth()) / 2, n)
        for z in self.b.Zones():
            if not z.GetIsRuleArea():
                continue
            o = z.Outline().Outline(0)
            pts = [(TM(o.CPoint(q).x), TM(o.CPoint(q).y)) for q in range(o.PointCount())]
            m = self.poly_mask(pts)
            for l in ALL:
                if z.IsOnLayer(L[l]) and z.GetDoNotAllowTracks():
                    self.noroute[l] |= m
            if z.GetDoNotAllowVias():
                self.novia |= m

    def add_via(self, x, y, r, dr, n):
        for l in ALL:
            self.disk(l, x, y, r, n)
        sl, m = self.disk_mask(x, y, dr)
        if sl is not None:
            self.hole[sl] |= m

    # ------------------------------------------------------------ free maps
    def free_map(self, layer, n, hw, clr):
        c = self.cop[layer]
        other = (c != 0) & (c != n)
        d = ndimage.distance_transform_edt(~other) * G
        free = d >= clr + hw + MARGIN
        free &= self.edge_dist >= self.edge + hw if hasattr(self, 'edge') else True
        free &= ~self.noroute[layer]
        return free

    def via_map(self, n, clr):
        r = self.via_d / 2
        ok = self.inside.copy()
        for l in ALL:
            c = self.cop[l]
            other = (c != 0) & (c != n)
            ok &= ndimage.distance_transform_edt(~other) * G >= clr + r + MARGIN
        ok &= ndimage.distance_transform_edt(~self.hole) * G >= 0.3 + self.via_drill / 2 + MARGIN
        ok &= ~self.smd
        ok &= ~self.novia
        ok &= self.edge_dist >= self.edge + r
        return ok

    edge = 0.5

    # ------------------------------------------------------------ search
    def _astar(self, free, viaok, starts, target, hmap, via_cost, own=None):
        """free: dict layer->bool array; starts: list of (li, j, i); target: dict layer->bool array"""
        nx, ny = self.nx, self.ny
        nl = len(self.layers)
        size = nx * ny
        fb = [free[l].tobytes() for l in self.layers]
        tb = [target[l].tobytes() for l in self.layers]
        vb = viaok.tobytes() if viaok is not None else None
        h = hmap.ravel().tolist()
        g = {}
        par = {}
        pq = []
        for li, j, i in starts:
            k = li * size + j * nx + i
            g[k] = 0.0
            heapq.heappush(pq, (h[j * nx + i], 0.0, k))
        moves = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0), (1, 1, SQ2), (1, -1, SQ2), (-1, 1, SQ2),
                 (-1, -1, SQ2)]
        cnt = 0
        while pq:
            f, gc, k = heapq.heappop(pq)
            if gc > g.get(k, 1e18):
                continue
            li, c = divmod(k, size)
            if tb[li][c]:
                path = [k]
                while k in par:
                    k = par[k]
                    path.append(k)
                return path[::-1]
            cnt += 1
            if cnt > 1500000:
                return None
            j, i = divmod(c, nx)
            fl = fb[li]
            for di, dj, w in moves:
                ii, jj = i + di, j + dj
                if ii < 0 or jj < 0 or ii >= nx or jj >= ny:
                    continue
                c2 = jj * nx + ii
                if not fl[c2] and not tb[li][c2]:
                    continue
                if w > 1.0 and not (fl[j * nx + ii] and fl[jj * nx + i]):
                    continue
                k2 = li * size + c2
                g2 = gc + w
                if g2 < g.get(k2, 1e18):
                    g[k2] = g2
                    par[k2] = k
                    heapq.heappush(pq, (g2 + h[c2], g2, k2))
            if vb is not None and vb[c]:
                for l2 in range(nl):
                    if l2 == li or not (fb[l2][c] or tb[l2][c]):
                        continue
                    k2 = l2 * size + c
                    g2 = gc + via_cost
                    if g2 < g.get(k2, 1e18):
                        g[k2] = g2
                        par[k2] = k
                        heapq.heappush(pq, (g2 + h[c], g2, k2))
        return None

    def _emit(self, path, net, w, n):
        """path of node keys -> tracks/vias on the board and in the raster"""
        size = self.nx * self.ny
        pts = []
        for k in path:
            li, c = divmod(k, size)
            j, i = divmod(c, self.nx)
            pts.append((li, i, j))
        runs = []
        cur = [pts[0]]
        for a, b in zip(pts, pts[1:]):
            if a[0] != b[0]:
                runs.append(cur)
                x, y = self.xy(a[1], a[2])
                self.B.via(net, x, y, self.via_d, self.via_drill, lock=False)
                self.add_via(x, y, self.via_d / 2, self.via_drill / 2, n)
                cur = [b]
            else:
                cur.append(b)
        runs.append(cur)
        for run in runs:
            if len(run) < 2:
                continue
            layer = self.layers[run[0][0]]
            simp = [run[0]]
            for q in range(1, len(run) - 1):
                a, b, c = run[q - 1], run[q], run[q + 1]
                if (b[1] - a[1], b[2] - a[2]) != (c[1] - b[1], c[2] - b[2]):
                    simp.append(b)
            simp.append(run[-1])
            xy = [self.xy(p[1], p[2]) for p in simp]
            self.B.track(net, layer, xy, w, lock=False)
            for (xa, ya), (xb, yb) in zip(xy, xy[1:]):
                self.seg(layer, xa, ya, xb, yb, w / 2, n)

    def pad_cells(self, ref, num):
        """cells (per routing layer) that lie in the pads ref.num, plus exact centre"""
        out = []
        for p in self.B.fp(ref).Pads():
            if p.GetNumber() != str(num):
                continue
            bb = p.GetBoundingBox()
            cx, cy = TM(p.GetPosition().x), TM(p.GetPosition().y)
            ls = [l for l in self.layers if p.IsOnLayer(L[l])]
            out.append((cx, cy, ls, (TM(bb.GetLeft()), TM(bb.GetTop()), TM(bb.GetRight()), TM(bb.GetBottom()))))
        return out

    def route_net(self, net, w=0.15, clr=0.2, via_cost=25, pads=None, order=None, allow_via=True):
        """connect all pads of the net (or the given (ref, num) list) into one tree"""
        n = self.nid(net)
        plist = []
        if pads is None:
            for f in self.b.GetFootprints():
                seen = set()
                for p in f.Pads():
                    if p.GetNetname() == net and p.GetNumber() not in seen:
                        seen.add(p.GetNumber())
                        plist.append((f.GetReference(), p.GetNumber()))
        else:
            plist = list(pads)
        free = {l: self.free_map(l, n, w / 2, clr) for l in self.layers}
        viaok = self.via_map(n, clr) if allow_via else None
        own = {l: self.cop[l] == n for l in self.layers}
        # connected components of own copper: the tree starts from the first pad's component
        info = []
        for ref, num in plist:
            cells = []
            for cx, cy, ls, bb in self.pad_cells(ref, num):
                i, j = self.ij(cx, cy)
                for l in ls:
                    cells.append((self.layers.index(l), j, i))
            if cells:
                info.append(((ref, num), cells))
        if len(info) < 2:
            return True
        # component labelling across layers (through pads/vias join layers at same cell)
        tree = {l: np.zeros((self.ny, self.nx), bool) for l in self.layers}

        def grow(seed):
            stack = list(seed)
            while stack:
                li, j, i = stack.pop()
                l = self.layers[li]
                if tree[l][j, i] or not own[l][j, i]:
                    continue
                lab, _ = ndimage.label(own[l], structure=np.ones((3, 3)))
                comp = lab == lab[j, i]
                tree[l] |= comp
                for l2i, l2 in enumerate(self.layers):
                    if l2 == l:
                        continue
                    both = comp & own[l2] & self.hole_or_via(n)
                    jj, ii = np.nonzero(both & ~tree[l2])
                    if len(jj):
                        stack.append((l2i, int(jj[0]), int(ii[0])))
                        for q in range(1, len(jj)):
                            stack.append((l2i, int(jj[q]), int(ii[q])))
        grow(info[0][1])
        todo = info[1:]
        ok = True
        while todo:
            # skip pads already in the tree
            rest = []
            for key, cells in todo:
                if any(tree[self.layers[li]][j, i] for li, j, i in cells):
                    continue
                rest.append((key, cells))
            todo = rest
            if not todo:
                break
            anyt = np.zeros((self.ny, self.nx), bool)
            for l in self.layers:
                anyt |= tree[l]
            hmap = ndimage.distance_transform_edt(~anyt)
            # nearest pad first
            todo.sort(key=lambda t: hmap[t[1][0][1], t[1][0][2]])
            key, cells = todo.pop(0)
            for l in self.layers:
                free[l] |= own[l]
            path = self._astar(free, viaok, cells, tree, hmap, via_cost)
            if path is None:
                self.failed.append((net, key))
                ok = False
                continue
            self._emit(path, net, w, n)
            own = {l: self.cop[l] == n for l in self.layers}
            grow(cells)
        return ok

    def hole_or_via(self, n):
        return self.hole

    def fanout(self, net, plane_mask=None, w=0.3, clr=0.2, pads=None, maxlen=60, skip_tht=True):
        """give every SMD pad of the net a short stub and a via (the plane connects the vias)"""
        n = self.nid(net)
        done = 0
        plist = []
        for f in self.b.GetFootprints():
            seen = set()
            for p in f.Pads():
                if p.GetNetname() != net or p.GetNumber() in seen:
                    continue
                if pads is not None and (f.GetReference(), p.GetNumber()) not in pads:
                    continue
                seen.add(p.GetNumber())
                if skip_tht and p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH:
                    continue
                plist.append((f.GetReference(), p.GetNumber()))
        for ref, num in plist:
            free = {l: self.free_map(l, n, w / 2, clr) | (self.cop[l] == n) for l in self.layers}
            viaok = self.via_map(n, clr)
            if plane_mask is not None:
                viaok &= plane_mask
            cells = []
            for cx, cy, ls, bb in self.pad_cells(ref, num):
                i, j = self.ij(cx, cy)
                for l in ls:
                    cells.append((self.layers.index(l), j, i))
            if not cells:
                continue
            li0 = cells[0][0]
            # target: via-able cells on the pad's own layer, or an existing via of the net
            target = {l: np.zeros((self.ny, self.nx), bool) for l in self.layers}
            target[self.layers[li0]] = viaok & free[self.layers[li0]]
            hmap = np.zeros((self.ny, self.nx), np.float32)
            path = self._astar(free, None, cells, target, hmap, 0)
            if path is None or len(path) > maxlen:
                self.failed.append((net, (ref, num), 'fanout'))
                continue
            if len(path) > 1:
                self._emit(path, net, w, n)
            size = self.nx * self.ny
            li, c = divmod(path[-1], size)
            j, i = divmod(c, self.nx)
            x, y = self.xy(i, j)
            self.B.via(net, x, y, self.via_d, self.via_drill, lock=False)
            self.add_via(x, y, self.via_d / 2, self.via_drill / 2, n)
            done += 1
        return done
