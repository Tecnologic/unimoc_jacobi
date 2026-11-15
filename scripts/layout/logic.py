"""Logic board: placement, planes, routing."""
from kl import Board, rect
from router import Router

# GNDA / +3.3VADC island (analog front end, LDO, analog connectors)
P = [(228.0, 73.4), (254.2, 73.4), (254.2, 68.6), (264.0, 68.6), (264.0, 116.2), (247.0, 116.2), (247.0, 103.3),
     (233.9, 103.3), (233.9, 91.6), (222.6, 91.6), (222.6, 83.7), (228.0, 83.7)]
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
    # CAN
    'U1101': (203.0, 97.0, 0), 'C1104': (207.4, 97.0, 90), 'R1108': (210.2, 96.2, 0), 'R1109': (210.2, 97.8, 0),
    'R1114': (192.9, 92.0, 0),
    # MCU supply
    'C608': (218.2, 89.0, 0), 'C620': (221.3, 89.0, 0), 'C609': (214.5, 106.0, 90), 'C603': (221.0, 104.5, 0),
    'C610': (235.2, 108.4, 90), 'C611': (231.8, 110.0, 180), 'C607': (233.4, 113.0, 0), 'C622': (237.0, 96.0, 0),
    'C621': (235.2, 105.3, 90), 'C606': (238.2, 96.1, -90), 'X601': (238.8, 105.4, 180), 'R612': (244.4, 105.3, 90),
    'FB502': (228.6, 82.6, 180),
    # analog inputs above the MCU (pins 32..36)
    'C704': (223.6, 88.3, -90), 'C716': (225.5, 88.3, -90), 'C717': (227.4, 88.3, -90), 'C719': (229.3, 88.3, -90),
    'C604': (231.2, 88.3, 90),
    'R705': (223.6, 85.3, 90), 'R720': (225.5, 85.3, 90), 'R721': (227.4, 85.3, 90), 'R723': (229.3, 85.3, 90),
    'R603': (231.2, 85.3, -90),
    # analog inputs right of the MCU (pins 15..25), one row per signal
    'C714': (238.2, 87.6, 180), 'C713': (238.2, 89.7, 180), 'C703': (238.2, 91.8, 180), 'C709': (238.2, 93.9, 0),
    'C718': (238.2, 98.1, 180), 'C715': (238.2, 100.2, 180), 'C602': (238.2, 102.3, 0),
    'R718': (241.4, 87.6, 0), 'R717': (241.4, 89.7, 0), 'R704': (241.4, 91.8, 0), 'R722': (241.4, 98.1, 0),
    'R719': (241.4, 100.2, 0), 'R602': (241.4, 102.3, 180), 'R703': (244.7, 91.8, 0), 'C701': (244.7, 89.7, 0),
    'R716': (243.8, 96.6, 0),
    # status LEDs
    'R1106': (236.8, 109.3, 90), 'D1101': (236.8, 112.6, 90), 'R1107': (238.6, 109.3, 90), 'D1102': (238.6, 112.6, 90),
    'R1110': (240.4, 109.3, 90), 'D1103': (240.4, 112.6, 90), 'R1111': (242.2, 109.3, 90), 'D1104': (242.2, 112.6, 90),
    # boot jumper
    'JP601': (224.6, 112.2, 0), 'R601': (227.6, 111.0, 90),
    # PWM series resistors (bottom side, next to J101)
    'R609': (196.4, 93.2, 0), 'R606': (196.4, 94.8, 0), 'R610': (196.4, 96.4, 0), 'R607': (196.4, 98.0, 0),
    'R608': (196.4, 107.6, 0), 'R611': (196.4, 109.2, 0),
}


def place(B: Board):
    for ref, (x, y, r) in PLACE.items():
        B.place(ref, x, y, r)
    for ref in ('J101', 'J102', 'J111', 'H101', 'H102', 'H103'):
        B.fp(ref).SetLocked(True)


PLANES = {'GNDD': False, '+3V3': False, 'GNDA': True, '+3.3VADC': True}   # net -> lives in the analog island
WIDTH = {'Default': 0.2, 'Analog': 0.2, 'USB': 0.2, 'Dig Supply': 0.4, 'Analog Supply': 0.4, 'GateDrive': 0.5}


def zones(B: Board):
    whole = rect(LX0, LY0, LX1, LY1)
    B.zone('GNDD', ['I1'], whole, prio=0, clr=0.25, name='GNDD plane', island='always')
    B.zone('GNDA', ['I1'], P, prio=1, clr=0.25, name='GNDA plane', island='always')
    B.zone('+3V3', ['I2'], whole, prio=0, clr=0.25, name='+3V3 plane', island='always')
    B.zone('+3.3VADC', ['I2'], P, prio=1, clr=0.25, name='+3.3VADC plane', island='always')
    for ly in ('F', 'B'):
        B.zone('GNDD', [ly], whole, prio=0, clr=0.25, name=f'GNDD pour {ly}', island='always')
        B.zone('GNDA', [ly], P, prio=1, clr=0.25, name=f'GNDA pour {ly}', island='always')
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
    # --- fine-pitch escapes and the USB-C connector by hand
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
    # --- MCU supply: analog pins to their capacitor, bottom-side capacitors to their pins
    R.route_net('+3.3VADC', w=0.25, pads=[('U601', '20'), ('U601', '21'), ('C622', '1')])
    R.route_net('GNDA', w=0.25, pads=[('U601', '19'), ('C622', '2')])
    special = set()
    for cap, vdd, vss in (('C601', '11', '10'), ('C612', '27', '26')):
        R.route_net('+3V3', w=0.25, pads=[('U601', vdd), (cap, '1')], via_mask=outside)
        R.route_net('GNDD', w=0.25, pads=[('U601', vss), (cap, '2')], via_mask=outside)
        special |= {('U601', vdd), ('U601', vss), (cap, '1'), (cap, '2')}
    # pin -> capacitor on the top side; the capacitor pads get the plane vias
    for cap, vdd, vss in (('C608', '50', '49'), ('C609', '75', '74'), ('C611', '100', '99')):
        R.route_net('+3V3', w=0.25, pads=[('U601', vdd), (cap, '1')], allow_via=False)
        R.route_net('GNDD', w=0.25, pads=[('U601', vss), (cap, '2')], allow_via=False)
        special |= {('U601', vdd), ('U601', vss)}
    R.route_net('+1V2', w=0.25)
    R.route_net('Net-(U601-PH0)', w=0.2)
    chip = R.poly_mask(rect(218.7, 93.2, 231.3, 105.8))
    for net in ('GNDD', '+3V3'):
        up = {q for q in nets[net]['pads'] if q[0] == 'U601'} - special
        R.fanout(net, plane_mask=chip, w=0.25, pads=up, maxlen=60)
    # --- plane fanouts of everything else
    for net, ana in PLANES.items():
        mask = core if ana else outside
        rest = {q for q in nets[net]['pads'] if q[0] != 'U601'} - special
        R.fanout(net, plane_mask=mask, w=0.4, pads=rest, maxlen=80)
    for item in list(R.failed):
        if len(item) == 3 and item[2] == 'fanout':
            R.failed.remove(item)
            R.join(item[0], item[1][0], item[1][1], w=0.25)
    R.route_net(DP, w=0.2)
    R.route_net(DM, w=0.2)
    R.route_net(VBUS, w=0.3)
    # --- signals: nets that failed in an earlier pass first, then MCU nets, short before long
    done = set(PLANES) | set(ISON) | {'+1V2', 'Net-(U601-PH0)', DP, DM, VBUS}
    todo = [nm for nm in nets if nm not in done and len(nets[nm]['pads']) > 1]
    span = lambda nm: (max(nets[nm]['xs']) - min(nets[nm]['xs'])) + (max(nets[nm]['ys']) - min(nets[nm]['ys']))
    fl = list(first)
    todo.sort(key=lambda nm: (fl.index(nm) if nm in fl else len(fl), not mcu(nm), span(nm)))
    for nm in todo:
        w = WIDTH.get(nets[nm]['cls'], 0.15)
        if w > 0.25 and mcu(nm):
            w = 0.25
        R.route_net(nm, w=w, via_cost=30)
    zones(B)
    return R
