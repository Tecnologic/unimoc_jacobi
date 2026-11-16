"""Logic board: placement, planes, routing."""
from kl import Board, rect
from router import Router

# GNDA / +3.3VADC island (analog front end, LDO, analog connectors)
P = [(228.0, 73.4), (254.2, 73.4), (254.2, 68.6), (264.0, 68.6), (264.0, 116.2), (247.0, 116.2), (247.0, 103.3),
     (235.9, 103.3), (235.9, 99.2), (233.9, 99.2), (233.9, 92.2), (235.6, 92.2), (235.6, 89.0), (232.2, 89.0), (232.2, 91.6), (222.6, 91.6),
     (222.6, 83.7), (228.0, 83.7)]
# isolated input side of the PWM_EN optocoupler: no pours
ISO = [(186.9, 73.0), (198.6, 73.0), (198.6, 89.8), (191.3, 89.8), (191.3, 77.4), (186.9, 77.4)]
LX0, LY0, LX1, LY1 = 180.25, 59.0, 264.25, 138.0

PLACE = {
    # board-to-board and edge connectors
    'J101': (187.37, 102.02, 90), 'J501': (188.5, 70.0, -90), 'J1103': (188.5, 81.2, -90),
    'J1104': (188.5, 108.9, -90), 'J601': (256.4, 77.6, 90),
    # PWM_EN optocoupler
    'R1115': (192.9, 78.5, 90), 'C1108': (192.9, 82.6, 90), 'D1105': (192.9, 87.0, 90), 'U1102': (198.6, 84.5, 0),
    'R1105': (205.0, 86.6, 0), 'R1101': (220.4, 86.4, -90), 'R1116': (218.8, 86.4, -90), 'C1109': (217.2, 86.4, -90),
    # 12 V buck (LM5008): input capacitor and diode right below the IC, inductor to the right
    'U502': (207.0, 70.0, 180), 'C501': (203.6, 75.6, -90), 'D501': (209.6, 76.0, -90), 'L502': (216.7, 72.5, 0),
    'C507': (212.6, 67.2, 180), 'C511': (224.6, 72.6, 0), 'R501': (201.7, 69.0, 180), 'C505': (201.7, 70.6, 0),
    'C502': (199.3, 72.0, 90), 'C503': (199.3, 69.0, 90), 'R502': (210.2, 66.6, -90),
    'R506': (208.2, 61.6, 0), 'C509': (208.2, 63.2, 0), 'R508': (205.0, 63.2, 0), 'R505': (211.4, 61.6, 0),
    'C513': (211.4, 63.2, 180), 'D506': (215.7, 62.6, 0), 'R513': (222.3, 78.6, 0), 'D504': (225.6, 78.6, 180),
    # 3.3 V buck (LMR12010): input capacitor left, diode below, inductor and output capacitors to the right
    'U501': (232.2, 64.6, 180), 'C504': (228.2, 65.6, -90), 'D505': (230.6, 69.8, 180), 'L501': (236.6, 69.8, 0),
    'C506': (232.2, 67.15, 0), 'D502': (237.1, 65.6, 0), 'R504': (236.3, 63.3, 0), 'R503': (236.3, 61.7, 180),
    'C508': (241.2, 70.1, -90), 'C510': (244.6, 70.1, -90), 'R507': (248.0, 67.5, -90), 'D503': (248.0, 64.3, -90),
    # +3.3VADC regulator
    'U503': (233.5, 76.0, 0), 'D507': (239.0, 76.0, 0), 'R509': (243.5, 76.0, 0), 'C514': (248.0, 76.0, 0),
    'C516': (252.5, 76.0, 0), 'R510': (229.0, 79.2, 0), 'R511': (232.6, 79.2, 0), 'C515': (236.2, 79.2, 0),
    'FB502': (228.6, 82.6, 180),
    # CAN
    'U1101': (195.5, 93.5, 0), 'C1104': (199.6, 93.5, 90), 'R1108': (202.4, 92.7, 0), 'R1109': (202.4, 94.3, 0),
    'R1114': (192.4, 90.6, 0),
    # PWM series resistors next to J101
    'R609': (198.0, 99.0, 0), 'R606': (198.0, 100.5, 0), 'R610': (198.0, 102.0, 0), 'R607': (198.0, 103.5, 0),
    'R608': (198.0, 105.0, 0), 'R611': (198.0, 106.5, 0),
    # MCU supply
    'C608': (218.2, 89.0, 0), 'C620': (221.3, 89.0, 0), 'C612': (233.6, 89.9, 180),
    'C609': (214.6, 107.6, 180), 'C603': (211.5, 107.6, 180),
    'C601': (235.0, 100.75, -90), 'C610': (227.8, 114.2, 0), 'C611': (231.8, 110.0, 180), 'C607': (231.8, 112.7, 0),
    'C622': (237.4, 96.0, 0), 'C605': (240.6, 96.0, 180), 'C606': (245.7, 96.0, 180),
    'C621': (224.2, 123.5, 90), 'X601': (242.4, 105.6, 180), 'R612': (245.8, 105.3, 90),
    # analog inputs above the MCU (pins 32..36)
    'C704': (223.6, 88.3, -90), 'C716': (225.5, 88.3, -90), 'C717': (227.4, 88.3, -90), 'C719': (229.3, 88.3, -90),
    'C604': (231.2, 88.3, 90),
    'R705': (223.6, 85.3, 90), 'R720': (225.5, 85.3, 90), 'R721': (227.4, 85.3, 90), 'R723': (229.3, 85.3, 90),
    'R603': (231.2, 85.3, -90),
    # analog inputs right of the MCU (pins 15..25), one row per signal
    'C714': (238.6, 87.6, 180), 'C713': (238.6, 89.7, 180), 'C703': (238.6, 91.8, 180), 'C709': (238.6, 93.9, 0),
    'C718': (238.6, 98.1, 180), 'C715': (238.6, 100.2, 180), 'C602': (238.6, 102.3, 0),
    'R718': (241.8, 87.6, 0), 'R717': (241.8, 89.7, 0), 'R704': (241.8, 91.8, 0), 'R716': (241.8, 93.9, 0),
    'R722': (241.8, 98.1, 0), 'R719': (241.8, 100.2, 0), 'R602': (241.8, 102.3, 180),
    'R703': (245.1, 91.8, 0), 'C701': (245.1, 89.7, 0),
    # status LEDs
    'R1106': (236.8, 110.6, 90), 'D1101': (236.8, 113.9, 90), 'R1107': (238.6, 110.6, 90), 'D1102': (238.6, 113.9, 90),
    'R1110': (240.4, 110.6, 90), 'D1103': (240.4, 113.9, 90), 'R1111': (242.2, 110.6, 90), 'D1104': (242.2, 113.9, 90),
    # boot jumper
    'JP601': (224.6, 112.2, 0), 'R601': (227.6, 111.0, 90),
}
# regulator pours on the top layer: net -> polygons
VIN = 'Net-(J501-Pin_2)'
POURS = [
    (VIN, [(198.8, 72.2), (204.05, 72.2), (204.05, 70.75), (205.75, 70.75), (205.75, 72.2), (206.35, 72.2),
           (206.35, 74.0), (200.85, 74.0), (200.85, 73.3), (198.8, 73.3)]),
    ('Net-(D501-K)', [(208.25, 70.72), (211.6, 70.72), (211.6, 68.55), (212.9, 68.55), (212.9, 66.65), (213.9, 66.65),
                      (213.9, 68.55), (214.9, 68.55), (214.9, 76.45), (211.6, 76.45), (211.6, 75.35), (208.6, 75.35),
                      (208.6, 71.25), (208.25, 71.25)]),
    ('+12V', [(218.55, 68.55), (224.8, 68.55), (224.8, 66.3), (226.3, 63.45), (231.8, 63.45), (231.8, 64.95),
              (229.75, 64.95), (229.75, 65.6), (226.9, 65.6), (226.9, 70.5), (224.0, 70.5), (224.0, 74.05),
              (221.8, 74.05), (221.8, 76.45), (218.55, 76.45)]),
    ('+12V', [(216.8, 61.7), (218.9, 61.7), (218.9, 68.7), (216.8, 68.7)]),
    ('Net-(D505-K)', [(230.35, 65.22), (231.9, 65.22), (231.9, 68.8), (235.6, 68.8), (235.6, 70.8), (231.3, 70.8),
                      (231.3, 68.8), (230.35, 68.8)]),
    ('+3V3', [(237.6, 64.7), (239.6, 64.7), (239.6, 67.95), (248.5, 67.95), (248.5, 69.3), (238.75, 69.3),
              (238.75, 70.8), (237.6, 70.8)]),
]
GND_VIAS = [(207.5, 77.0), (207.5, 78.2), (227.4, 72.0), (227.4, 73.2), (226.5, 69.3), (226.5, 70.4),
            (239.2, 71.6), (246.6, 71.6), (203.6, 79.3), (209.6, 79.5)]


def place(B: Board):
    import pcbnew
    for ref, (x, y, r) in PLACE.items():
        f = B.fp(ref)
        if f.IsFlipped() and ref != 'J101':
            f.SetLayerAndFlip(pcbnew.F_Cu)      # all parts on top, only the board-to-board headers stay below
        B.place(ref, x, y, r)
    for ref in ('J101', 'J102', 'J111', 'H101', 'H102', 'H103', 'J103', 'J104', 'J110'):
        B.fp(ref).SetLocked(True)
    # the rule areas under the inductors move with them
    for z in list(B.b.Zones()):
        if z.GetIsRuleArea():
            B.b.Delete(z)
    B.keepout(['F', 'I1', 'I2', 'B'], rect(215.1, 69.0, 218.3, 76.0), tracks=False, vias=False, copper=True,
              name='under L502')
    B.keepout(['F', 'I1', 'I2', 'B'], rect(235.85, 68.8, 237.35, 70.8), tracks=True, vias=True, copper=True,
              name='under L501')


PLANES = {'GNDD': False, '+3V3': False, 'GNDA': True, '+3.3VADC': True}   # net -> lives in the analog island
WIDTH = {'Default': 0.2, 'Analog': 0.2, 'USB': 0.2, 'Dig Supply': 0.5, 'Analog Supply': 0.5, 'GateDrive': 0.5}


def zones(B: Board):
    whole = rect(LX0, LY0, LX1, LY1)
    B.zone('GNDD', ['I1'], whole, prio=0, clr=0.25, name='GNDD plane', island='always')
    B.zone('GNDA', ['I1'], P, prio=1, clr=0.25, name='GNDA plane', island='always')
    B.zone('+3V3', ['I2'], whole, prio=0, clr=0.25, name='+3V3 plane', island='always')
    B.zone('+3.3VADC', ['I2'], P, prio=1, clr=0.25, name='+3.3VADC plane', island='always')
    for ly in ('F', 'B'):
        # 0.5 mm minimum width: no thin fingers between the tracks
        B.zone('GNDD', [ly], whole, prio=0, clr=0.25, minw=0.5, name=f'GNDD pour {ly}', island='always')
        B.zone('GNDA', [ly], P, prio=1, clr=0.25, minw=0.5, name=f'GNDA pour {ly}', island='always')
    for k, (net, pts) in enumerate(POURS):
        B.zone(net, ['F'], pts, prio=5 + k, clr=0.3, minw=0.25, name=f'{net} regulator', island='never')
    B.keepout(['F', 'I1', 'I2', 'B'], ISO, tracks=False, vias=False, copper=True, name='PWM_EN isolation')


def route(B: Board, first=()):
    b = B.b
    R = Router(B, (180.2, 59.0, 264.3, 138.0), layers=('F', 'B'))
    inP = R.poly_mask(P)
    from scipy import ndimage
    core = ndimage.binary_erosion(inP, iterations=7)
    outside = ndimage.binary_erosion(~inP, iterations=7)
    # --- isolated optocoupler input first, then nobody else may enter
    ISON = ('/logic/PWM_EN_IN', '/logic/PWM_EN_RTN', 'Net-(D1105-K)')
    for net in ISON:
        R.route_net(net, w=0.3, clr=0.3, allow_via=False)
    R.keepout(ISO)
    R.keepout(rect(214.9, 68.8, 218.5, 76.2), tracks=False)       # no vias in the copper-free areas
    R.keepout(rect(235.6, 68.6, 237.6, 71.0), tracks=False)       # under the inductors
    # --- nets of the logic board
    nets = {}
    for f in b.GetFootprints():
        if f.GetPosition().x / 1e6 > 270:
            continue
        for p in f.Pads():
            nm = p.GetNetname()
            if not nm or nm.startswith('unconnected'):
                continue
            d = nets.setdefault(nm, {'cls': p.GetNetClassName(), 'pads': set(), 'xs': [], 'ys': []})
            d['pads'].add((f.GetReference(), p.GetNumber()))
            d['xs'].append(p.GetPosition().x / 1e6)
            d['ys'].append(p.GetPosition().y / 1e6)
    mcu = lambda nm: any(r == 'U601' for r, _ in nets[nm]['pads'])
    # --- regulator pours are copper for the router; ground vias at the power parts
    for net, pts in POURS:
        R.fill_poly(net, 'F', pts)
    for x, y in GND_VIAS:
        R.manual_via('GNDD', x, y)
    # --- the USB-C connector by hand
    DP, DM, VBUS = '/logic/controller/mcu/USB_DP', '/logic/controller/mcu/USB_DM', '/logic/controller/usb/VBUS'
    px = 188.545
    fan = [('Net-(J602-CC1)', 122.25, 189.7, 121.4), (DM, 122.75, 190.1, 122.2), (DP, 123.25, 190.5, 123.0),
           (DM, 123.75, 190.5, 124.0), (DP, 124.25, 190.1, 124.8), ('Net-(J602-CC2)', 125.25, 189.7, 125.6)]
    for net, y, xt, yl in fan:
        R.manual(net, 'F', [(px, y), (xt, y), (xt + abs(yl - y), yl), (191.2, yl)], 0.2)
    R.manual(DM, 'F', [(191.2, 122.2), (191.6, 122.2)], 0.2)
    R.manual(DM, 'F', [(191.2, 124.0), (191.6, 124.0)], 0.2)
    R.manual_via(DM, 191.6, 122.2)
    R.manual_via(DM, 191.6, 124.0)
    R.manual(DM, 'B', [(191.6, 122.2), (191.6, 124.0)], 0.2)
    R.manual(DP, 'F', [(191.2, 123.0), (192.6, 123.0), (192.6, 124.8), (191.2, 124.8)], 0.2)
    R.manual(VBUS, 'F', [(px, 121.05), (189.5, 121.05)], 0.3)
    R.manual(VBUS, 'F', [(px, 125.95), (189.5, 125.95)], 0.3)
    # --- MCU supply: every pin pair to its capacitor on the top side, the capacitor pads get the plane vias
    R.route_net('+3.3VADC', w=0.25, pads=[('U601', '20'), ('U601', '21'), ('C622', '1')], allow_via=False)
    R.route_net('GNDA', w=0.25, pads=[('U601', '19'), ('C622', '2')], allow_via=False)
    special = set()
    for cap, vdd, vss in (('C608', '50', '49'), ('C609', '75', '74'), ('C611', '100', '99'), ('C612', '27', '26'),
                          ('C601', '11', '10')):
        R.route_net('+3V3', w=0.25, pads=[('U601', vdd), (cap, '1')], allow_via=False)
        R.route_net('GNDD', w=0.25, pads=[('U601', vss), (cap, '2')], allow_via=False)
        special |= {('U601', vdd), ('U601', vss)}
    # VBAT and the pin pair of C601 (which sits in the analog area): plane vias under the MCU
    chip = R.poly_mask(rect(218.7, 93.2, 231.3, 105.8))
    R.fanout('+3V3', plane_mask=chip, w=0.25, pads={('U601', '6')}, maxlen=60)
    # neighbouring pins 11 and 10: the two vias are staggered by hand, they do not fit side by side
    R.manual('+3V3', 'F', [(232.675, 100.5), (231.5, 100.5), (231.0, 100.0)], 0.25)
    R.manual_via('+3V3', 231.0, 100.0)
    R.manual('GNDD', 'F', [(232.675, 101.0), (231.5, 101.0), (231.1, 101.4)], 0.25)
    R.manual_via('GNDD', 231.1, 101.4)
    special |= {('U601', '6'), ('C601', '1'), ('C601', '2')}
    R.route_net('+1V2', w=0.25)
    R.route_net('Net-(U601-PH0)', w=0.2)
    # --- plane fanouts
    for net, ana in PLANES.items():
        mask = core if ana else outside
        rest = nets[net]['pads'] - special - {('U601', '19'), ('U601', '20'), ('U601', '21')}
        R.fanout(net, plane_mask=mask, w=0.5, pads=rest, maxlen=80)
    for item in list(R.failed):
        if len(item) == 3 and item[2] == 'fanout':
            R.failed.remove(item)
            R.join(item[0], item[1][0], item[1][1], w=0.25)
    R.route_net(DP, w=0.2)
    R.route_net(DM, w=0.2)
    R.route_net(VBUS, w=0.3)
    # --- supplies: 12 V with a 1 mm trunk to the power board connector, like on the power board
    R.route_net('+12V', w=1.0, via_cost=60, pads=[('C511', '1'), ('J101', '5')])
    R.route_net('+12V', w=0.5, via_cost=40)
    R.route_net(VIN, w=0.8, via_cost=40)
    R.route_net('+BATT_LOGIC', w=0.8, via_cost=40)
    # --- signals: nets that failed in an earlier pass first, then MCU nets, short before long
    done = set(PLANES) | set(ISON) | {'+1V2', 'Net-(U601-PH0)', DP, DM, VBUS, '+12V', VIN, '+BATT_LOGIC'}
    todo = [nm for nm in nets if nm not in done and len(nets[nm]['pads']) > 1]
    span = lambda nm: (max(nets[nm]['xs']) - min(nets[nm]['xs'])) + (max(nets[nm]['ys']) - min(nets[nm]['ys']))
    fl = list(first)
    todo.sort(key=lambda nm: (fl.index(nm) if nm in fl else len(fl), not mcu(nm), span(nm)))
    for nm in todo:
        w = WIDTH.get(nets[nm]['cls'], 0.2)
        if w > 0.25 and mcu(nm):
            w = 0.25
        R.hug = not mcu(nm) and nm not in fl      # bundle the long runs; the MCU escapes take the direct way
        R.route_net(nm, w=w, via_cost=30)
    # --- ground vias: every piece of the top and bottom pours is tied to the plane
    print('stitching vias', R.stitch('GNDD', outside), R.stitch('GNDA', core))
    zones(B)
    return R
