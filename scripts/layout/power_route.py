"""Small-signal routing of the power board with the grid router."""
from kl import rect
from router import Router
from power import CELLS, PITCH


TRUNK = 1.0      # width of the +12P trunk


def route(B):
    R = Router(B, (284.3, 59.0, 368.3, 138.0), layers=('F', 'I1', 'B'))
    R.hug = False
    # FET block and capacitor column: pours and scripted gate routing only
    R.keepout(rect(301.6, 59, 344.85, 138))
    # inner GND plane stays whole left of the analog part
    R.keepout(rect(284, 59, 345.0, 138), layers=['I1'], vias=False)
    # battery terminal pours
    R.keepout(rect(285.5, 72.4, 302, 81.8), layers=['F'])
    R.keepout(rect(288.7, 72.3, 302, 81.9), layers=['B'])
    for i, (n, l, dyc, sy, term) in enumerate(CELLS):
        ty = B.fp(term).GetPosition().y / 1e6
        R.keepout(rect(344.5, sy - 3.9, 348.7, sy + 3.9), layers=['F', 'B'])
        m = 0.35
        if abs(ty - sy) < 0.1:
            ph = rect(352.95 - m, sy - 4.4 - m, 368.3, sy + 4.4 + m)
        else:
            ph = [(352.95 - m, sy - 3.6 - m), (358.4 - m, sy - 3.6 - m), (358.4 - m, ty - 4.3 - m), (368.3, ty - 4.3 - m),
                  (368.3, ty + 4.7 + m), (358.4 - m, ty + 4.7 + m), (358.4 - m, sy + 3.5 + m), (352.95 - m, sy + 3.5 + m)]
        R.keepout(ph, layers=['F', 'B'])
    # PWM inputs and the +12P trunk as the board owner routed them by hand (commit 59841ef);
    # +12P is widened to 1 mm
    import json, os
    have = set()
    for t in B.b.GetTracks():
        if t.GetClass() != 'PCB_VIA':
            have.add((t.GetNetname(), round(t.GetStart().x / 1e6, 2), round(t.GetStart().y / 1e6, 2),
                      round(t.GetEnd().x / 1e6, 2), round(t.GetEnd().y / 1e6, 2)))
    items = json.load(open(os.path.join(os.path.dirname(__file__), 'owner_tracks.json')))
    items.sort(key=lambda o: o['net'] == '+12P')            # the others first, then +12P as wide as they allow
    import numpy as np
    from scipy import ndimage
    from router import G
    dist = {}
    for o in items:
        n = R.nid(o['net'])
        trunk = o['net'] == '+12P'
        if 'via' in o:
            d, dr = (0.8, 0.4) if trunk else (o['d'], o['drill'])
            B.via(o['net'], o['via'][0], o['via'][1], d, dr)
            R.add_via(o['via'][0], o['via'][1], d / 2, dr / 2, n)
            continue
        k = (o['net'], round(o['a'][0], 2), round(o['a'][1], 2), round(o['b'][0], 2), round(o['b'][1], 2))
        if k in have or (k[0], k[3], k[4], k[1], k[2]) in have:
            continue
        w = o['w']
        if trunk:
            ly = o['layer']
            if ly not in dist:      # distance to foreign copper once all other tracks are in
                c = R.cop[ly]
                dist[ly] = ndimage.distance_transform_edt(~((c != 0) & (c != n))) * G
            (xa, ya), (xb, yb) = o['a'], o['b']
            m = max(2, int(max(abs(xb - xa), abs(yb - ya)) / 0.05))
            dmin = min(dist[ly][R.ij(xa + (xb - xa) * q / m, ya + (yb - ya) * q / m)[::-1]] for q in range(m + 1))
            for cand in (TRUNK, 0.8, 0.6, 0.5):
                if dmin >= cand / 2 + 0.25 + 0.08:
                    w = cand
                    break
        B.track(o['net'], o['layer'], [tuple(o['a']), tuple(o['b'])], w, chamfer=0)
        R.seg(o['layer'], o['a'][0], o['a'][1], o['b'][0], o['b'][1], w / 2, n)
    for l in 'ABC':
        for s in 'HL':
            R.route_net(f'/power/PWM_{l}{s}', w=0.2)
    R.route_net('/power/V12P_SNS', w=0.2)
    # gate driver supply: 1 mm trunk from the connector to the three drivers, then the small pads
    R.route_net('+12P', w=0.5, via_cost=40)
    R.route_net('Net-(J104-Pin_8)', w=0.2)
    for net in ('/power/I_A', '/power/I_B', '/power/I_C', '/power/VSENSE_A', '/power/VSENSE_B',
                '/power/VSENSE_C', '/power/VSENSE_DC'):
        R.route_net(net, w=0.2)
    R.route_net('+3.3VA', w=0.4, via_cost=40)
    ana = R.poly_mask([(345.4, 59.6), (360.5, 59.6), (360.5, 66.7), (367.7, 66.7), (367.7, 131.0), (345.4, 131.0)])
    pads = set()
    for f in B.b.GetFootprints():
        if f.GetReference() == 'TH101':
            continue
        for q in f.Pads():
            if q.GetNetname() == 'GND':
                pads.add((f.GetReference(), q.GetNumber()))
    R.fanout('GND', plane_mask=ana, w=0.25, pads=pads)
    return R
