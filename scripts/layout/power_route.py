"""Small-signal routing of the power board with the grid router."""
from kl import rect
from router import Router
from power import CELLS, PITCH


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
    for l in 'ABC':
        for s in 'HL':
            R.route_net(f'/power/PWM_{l}{s}', w=0.2)
    R.route_net('/power/V12P_SNS', w=0.2)
    # gate driver supply: 1 mm trunk from the connector to the three drivers, then the small pads
    R.route_net('+12P', w=1.0, via_cost=60, pads=[('J103', '5'), ('D301', '2'), ('D201', '2'), ('D401', '2')])
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
