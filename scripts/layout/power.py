"""Power board: placement, gate routing, pours and via fields."""
from kl import Board, Checker, rect, grid

X1, X2 = 318.8, 336.3            # FET columns
PITCH = 26.4
CELLS = [  # n, letter, cluster offset, shunt y, terminal ref
    (2, 'a', 0.0, 74.7, 'J106'),
    (3, 'b', 24.4, 101.1, 'J107'),
    (4, 'c', 58.9, 125.5, 'J108'),
]
GW = 0.5   # gate drive track width
BX0, BY0, BX1, BY1 = 284.3, 59.0, 368.3, 138.0
E = 0.3


def power(B: Board):
    b = B
    lanes = []   # (y, x0, x1) of horizontal inner-layer gate lanes in the capacitor column

    # ---------------------------------------------------------- placement
    b.place('Q401', X1, 131.5)          # was 131.84, now on the cell pitch like Q403
    for i, (n, l, dyc, sy, term) in enumerate(CELLS):
        dy = PITCH * i
        ys, yg = 63.36 + dy, 75.86 + dy
        r0 = 64.25 + dyc
        R = lambda k: f'R{n}{k:02d}'
        # low side, column 1
        b.place(R(5), 314.6, ys - 1.76, 180)
        b.place(R(12), 314.6, ys - 3.3, 180)
        b.place(R(6), 312.2, ys - 3.3, 0)
        # low side, column 2 (in the centre column, clear of the mounting holes)
        co = 0.4 if i == 0 else 0.0   # cell A: clear of the mounting hole H105
        b.place(R(7), 329.7, ys + 3.3 + co, 180)
        b.place(R(14), 329.7, ys + 4.9 + co, 180)
        b.place(R(8), 327.2, ys + 4.9 + co, 0)
        # high side, column 1
        b.place(R(3), 314.6, yg - 1.6, 180)
        b.place(R(11), 314.6, yg - 3.2, 180)
        b.place(R(4), 319.44, yg - 1.65, -90)
        # high side, column 2
        b.place(R(9), 332.1, yg - 1.6, 180)
        b.place(R(13), 332.1, yg - 3.2, 180)
        b.place(R(10), 336.94, yg - 1.65, -90)
        # commutation capacitor in the centre column
        b.place(f'C{n}04', 327.6, ys + 9.8, 90)
        # gate driver cluster
        b.place(f'U{n}01', 295.3, r0 + 0.635, 0)
        b.place(f'C{n}03', 300.6, r0, -90)
        b.place(f'D{n}01', 295.85, r0 - 3.85, 180)
        b.place(f'C{n}02', 292.0, r0 + 4.35, 0)
        b.place(f'C{n}01', 292.25, r0 + 6.25, 0)
        # current sense amplifier above the shunt, inputs facing it
        uy = sy - 7.6
        b.place(f'U{n}02', 350.3, uy, 90)
        b.place(f'C{n}05', 353.65, uy - 2.86, 0)
    # voltage dividers
    b.place('R101', 357.15, 79.9, -90); b.place('R102', 357.15, 83.2, -90); b.place('C101', 355.45, 83.2, 90)
    b.place('R103', 357.15, 105.5, -90); b.place('R104', 357.15, 108.8, -90); b.place('C102', 355.45, 108.8, 90)
    b.place('R105', 357.15, 121.0, 90); b.place('R106', 357.15, 117.7, 90); b.place('C103', 355.45, 117.7, -90)
    b.place('R107', 344.5, 110.4, 0); b.place('R108', 347.75, 110.4, 0); b.place('C104', 347.75, 112.0, 180)
    b.place('TH101', 324.55, 63.36 + PITCH - 1.5, -90)

    # ---------------------------------------------------------- gate drive
    for i, (n, l, dyc, sy, term) in enumerate(CELLS):
        dy = PITCH * i
        ys, yg = 63.36 + dy, 75.86 + dy
        r0 = 64.25 + dyc
        HO, HS, LO, VSS = (f'/power/phase_{l}/{s}' for s in ('HO', 'HS', 'LO', 'VSS'))
        HB = f'Net-(D{n}01-K)'
        SW = f'Net-(Q{n}02-D)'
        g = lambda k: f'Net-(Q{n}{k:02d}-G)'
        ux = 295.3
        # --- driver cluster, F.Cu
        # HB: diode cathode -> pin 8 -> bootstrap capacitor
        b.track(HB, 'F', [(297.85, r0 - 3.85), (297.775, r0 - 2.9), (297.775, r0 - 1.27)], GW)
        b.track(HB, 'F', [(297.775, r0 - 1.27), (299.3, r0 - 1.27), (300.6, r0 - 1.475)], GW)
        # HO straight out between the capacitor pads to its via
        b.track(HO, 'F', [(ux + 2.475, r0), (302.8, r0)], GW)
        b.via(HO, 302.8, r0)
        # HS into the capacitor pad, via behind it
        b.track(HS, 'F', [(ux + 2.475, r0 + 1.27), (299.4, r0 + 1.27), (300.6, r0 + 1.475)], GW)
        b.track(HS, 'F', [(300.6, r0 + 1.475), (301.3, r0 + 0.8), (302.0, r0 + 0.8)], GW)
        b.via(HS, 302.0, r0 + 0.8)
        # LO below the capacitor, then up to its lane
        b.track(LO, 'F', [(ux + 2.475, r0 + 2.54), (298.4, r0 + 3.15), (301.9, r0 + 3.15), (303.45, r0 + 1.6),
                          (303.7, r0 + 1.6)], GW)
        b.via(LO, 303.7, r0 + 1.6)
        # VSS: pin 4 -> decoupling capacitors -> lane
        b.track(VSS, 'F', [(ux - 2.475, r0 + 2.54), (292.775, r0 + 3.4), (292.775, r0 + 4.35)], GW)
        b.track(VSS, 'F', [(292.775, r0 + 4.35), (293.725, r0 + 5.4), (293.725, r0 + 6.25)], GW)
        b.track(VSS, 'F', [(292.775, r0 + 4.35), (293.3, r0 + 4.05), (302.4, r0 + 4.05), (303.95, r0 + 2.5),
                           (304.3, r0 + 2.4)], GW)
        b.via(VSS, 304.3, r0 + 2.4)
        # +12P: diode anode -> pin 1 -> decoupling capacitors
        P12 = '+12P'
        b.track(P12, 'F', [(293.85, r0 - 3.85), (292.825, r0 - 2.6), (292.825, r0 - 1.27)], GW)
        b.track(P12, 'F', [(292.825, r0 - 1.27), (291.8, r0 - 1.27), (291.225, r0 - 0.7), (291.225, r0 + 4.35),
                           (290.775, r0 + 5.2), (290.775, r0 + 6.25)], GW)
        # --- inner lanes through the capacitor column
        b.track(HO, 'I2', [(302.8, r0), (312.7, r0), (312.7, yg - 3.76), (330.0, yg - 3.76)], GW)
        b.track(HS, 'I2', [(302.0, r0 + 0.8), (311.85, r0 + 0.8), (311.85, yg - 2.96), (336.94, yg - 2.96)], GW)
        co = 0.4 if i == 0 else 0.0
        b.track(LO, 'I1', [(303.7, r0 + 1.6), (311.0, r0 + 1.6), (311.0, yg - 1.7), (324.6, yg - 1.7),
                           (324.6, ys + 3.3 + co)], GW)
        b.track(VSS, 'I1', [(304.3, r0 + 2.4), (310.2, r0 + 2.4), (310.2, yg - 0.9), (326.0, yg - 0.9),
                            (326.0, ys + 4.9 + co)], GW)
        for k in range(4):
            lanes.append((r0 + 0.8 * k, 301.5, 311.6))
        # --- low side column 1
        b.via(LO, 311.0, r0 + 1.6)
        b.via(VSS, 310.2, r0 + 2.4)
        b.track(LO, 'F', [(311.0, r0 + 1.6), (311.0, ys - 1.36), (311.4, ys - 1.76), (313.775, ys - 1.76)], GW)
        b.track(VSS, 'F', [(310.2, r0 + 2.4), (310.2, ys - 2.8), (310.7, ys - 3.3), (311.7, ys - 3.3)], GW)
        b.track(g(2), 'F', [(315.425, ys - 3.3), (315.425, ys - 0.5), (315.925, ys), (316.9, ys)], GW)
        # --- low side column 2
        b.via(LO, 324.6, ys + 3.3 + co)
        b.via(VSS, 326.0, ys + 4.9 + co)
        b.track(LO, 'F', [(324.6, ys + 3.3 + co), (328.875, ys + 3.3 + co)], GW)
        b.track(VSS, 'F', [(326.0, ys + 4.9 + co), (326.7, ys + 4.9 + co)], GW)
        b.track(g(4), 'F', [(330.525, ys + 4.9 + co), (330.525, ys + 3.3 + co), (331.15, ys + 2.675 + co), (331.15, ys + 0.95),
                            (332.1, ys), (334.4, ys)], GW)
        # --- high side column 1
        b.via(HO, 312.7, yg - 3.76)
        b.track(HO, 'F', [(312.7, yg - 3.76), (312.7, yg - 2.1), (313.2, yg - 1.6), (313.775, yg - 1.6)], GW)
        b.via(HS, 319.44, yg - 2.96)
        b.track(HS, 'F', [(319.44, yg - 2.96), (319.44, yg - 2.15)], GW)
        b.track(g(1), 'F', [(315.425, yg - 3.2), (315.425, yg - 0.5), (315.925, yg), (316.9, yg)], GW)
        # --- high side column 2
        b.via(HO, 330.0, yg - 3.76)
        b.track(HO, 'F', [(330.0, yg - 3.76), (330.0, yg - 2.3), (330.7, yg - 1.6), (331.275, yg - 1.6)], GW)
        b.via(HS, 336.94, yg - 2.96)
        b.track(HS, 'F', [(336.94, yg - 2.96), (336.94, yg - 2.15)], GW)
        b.track(g(3), 'F', [(332.925, yg - 3.2), (332.925, yg - 0.5), (333.425, yg), (334.4, yg)], GW)
        # --- Kelvin pair of the shunt to the amplifier
        uy = sy - 7.6
        SN = f'Net-(U{n}02--)'
        PH = f'/power/PHASE_{l.upper()}'
        b.track(SN, 'F', [(347.2, sy - 2.6), (350.625, sy - 2.6), (350.625, uy + 2.862)], 0.2)
        b.track(PH, 'F', [(353.4, sy - 2.6), (352.2, sy - 2.6), (352.2, uy + 1.3), (349.975, uy + 1.3),
                          (349.975, uy + 2.862)], 0.2)

    # bridge NTC pair out of the FET block (signal continues to J104 by the router)
    yn = 63.36 + PITCH
    b.track('Net-(J104-Pin_8)', 'F', [(324.55, yn - 2.325), (324.55, yn - 4.01), (346.6, yn - 4.01)], 0.2)
    b.track('GND', 'F', [(324.55, yn - 0.675), (323.65, yn - 1.4), (323.65, yn - 4.1), (324.05, yn - 4.5),
                         (346.6, yn - 4.5)], 0.2)
    # DC link divider feed
    b.track('+BATT', 'F', [(340.9, 109.6), (342.6, 109.6), (343.4, 110.4), (343.588, 110.4)], 0.4)
    b.track('/power/VSENSE_DC', 'F', [(345.412, 110.4), (346.925, 110.4)], 0.25)
    b.track('/power/VSENSE_DC', 'F', [(346.925, 110.4), (346.975, 112.0)], 0.25)
    b.track('+BATT', 'F', [(296.5, 104.54), (296.5, 107.0), (297.5, 107.0)], 0.5)

    # ---------------------------------------------------------- zones
    PW = 0.5   # clearance of the power pours
    whole = rect(BX0 + E, BY0 + E, BX1 - E, BY1 - E)
    for ly in ('F', 'I1', 'B'):
        b.zone('GNDPWR', [ly], whole, prio=0, clr=0.3, name=f'GNDPWR base {ly}', island='always')
    b.zone('+BATT', ['I2'], whole, prio=0, clr=PW, name='+BATT plane', island='always')
    # analog ground island on the right
    ana = [(344.9, 59.3), (360.9, 59.3), (360.9, 66.3), (368.0, 66.3), (368.0, 131.3), (344.9, 131.3)]
    for ly in ('F', 'I1', 'I2', 'B'):
        b.zone('GND', [ly], ana, prio=1, clr=0.3, name=f'GND analog {ly}', island='always')
    # GNDPWR link to the upper right housing pad
    b.zone('GNDPWR', ['B'], rect(341.0, 59.3, 361.4, 60.7), prio=2, clr=0.3, name='GNDPWR corner link')
    # battery terminal
    b.zone('+BATT', ['F'], rect(286.0, 72.9, 302.6, 81.3), prio=6, clr=PW, name='+BATT terminal F')
    b.zone('+BATT', ['B'], rect(289.0, 72.7, 313.9, 81.5), prio=6, clr=PW, name='+BATT terminal B')
    for i, (n, l, dyc, sy, term) in enumerate(CELLS):
        dy = PITCH * i
        ys, yg = 63.36 + dy, 75.86 + dy
        SW = f'Net-(Q{n}02-D)'
        PH = f'/power/PHASE_{l.upper()}'
        top = max(ys - 4.1, BY0 + E)
        nxt = min(ys + PITCH + 0.75, BY1 - E)
        sw = [(313.3, ys + 1.3), (344.6, ys + 1.3), (344.6, sy - 3.5), (348.3, sy - 3.5), (348.3, sy + 3.5),
              (341.3, sy + 3.5), (341.3, yg + 1.05), (313.3, yg + 1.05)]
        b.zone(SW, ['F', 'I2', 'B'], sw, prio=2, clr=PW, name=f'SW {l}', island='always')
        b.zone('GNDPWR', ['F'], rect(311.2, top, 343.9, ys + 0.95), prio=2, clr=0.3, name=f'GNDPWR source {l}')
        b.zone('GNDPWR', ['F'], rect(323.95, top, 331.25, ys + 8.2), prio=3, clr=0.3, name=f'GNDPWR centre {l}')
        b.zone('+BATT', ['F'], rect(302.2, yg + 1.25, 341.1, min(yg + 8.55, BY1 - E)), prio=2, clr=PW,
               name=f'+BATT drain {l}')
        b.zone('+BATT', ['F'], rect(324.5, yg - 1.35, 330.7, yg + 1.3), prio=3, clr=PW, name=f'+BATT cap {l}')
        b.zone('+BATT', ['B'], rect(313.5, yg + 1.25, 341.3, nxt), prio=2, clr=PW, island='always', name=f'+BATT drain B {l}')
        # phase output from the shunt to the terminal
        tx, ty, _ = b.pad(term, 1)
        ty = b.fp(term).GetPosition().y / 1e6
        if abs(ty - sy) < 0.1:
            ph = rect(352.95, sy - 4.4, 368.0, sy + 4.4)
        else:
            a, c = min(sy - 4.1, ty - 4.3), max(sy + 3.5, ty + 4.7)
            ph = [(352.95, sy - 3.6), (358.4, sy - 3.6), (358.4, ty - 4.3), (368.0, ty - 4.3), (368.0, ty + 4.7),
                  (358.4, ty + 4.7), (358.4, sy + 3.5), (352.95, sy + 3.5)]
        b.zone(PH, ['F', 'I2', 'B'], ph, prio=2, clr=PW, name=f'PHASE {l}')
    # electrolytic capacitor pads
    for n in (2, 3, 4):
        for c in (7, 9):
            for pn in (1, 2):
                x, y, net = b.pad(f'C{n}{c:02d}', pn)
                b.zone(net, ['F'], rect(303.3, y - 2.1, 308.75, y + 2.1), prio=4, clr=PW if net == '+BATT' else 0.3,
                       name=f'{net} C{n}{c:02d}')

    # ---------------------------------------------------------- via fields
    ck = Checker(b)

    def put(net, pts, d=0.8, drill=0.4, clr=0.3, gap=None):
        k = 0
        for x, y in pts:
            if ck.ok(x, y, d / 2, net, clr=clr, drill=drill / 2, same_pad_gap=gap):
                b.via(net, x, y, d, drill)
                ck.add_via(x, y, d / 2, drill / 2, net)
                k += 1
        return k

    cnt = {}
    for i, (n, l, dyc, sy, term) in enumerate(CELLS):
        dy = PITCH * i
        ys, yg = 63.36 + dy, 75.86 + dy
        SW = f'Net-(Q{n}02-D)'
        PH = f'/power/PHASE_{l.upper()}'
        k = 0
        for cx in (X1, X2):
            # source vias of the low-side FETs
            k += put('GNDPWR', grid(cx - 1.25, cx + 4.45, 0.95, ys - 2.75, ys - 1.75, 1.0), gap=0.15)
            k += put('GNDPWR', [(cx + 3.1, ys), (cx + 4.05, ys)], gap=0.15)
            # switch node vias next to the high-side sources
            put(SW, [(cx + 3.1, yg + 0.6), (cx + 4.05, yg + 0.6)], gap=0.15)
        cnt[f'GND src {l}'] = k
        # commutation capacitor
        put('GNDPWR', [(x, ys + 5.85) for x in (327.1, 328.1, 329.1, 330.1)] + [(330.95, ys + 7.3), (330.95, ys + 8.2)], gap=0.0)
        put('+BATT', [(x, yg + 1.4) for x in (325.6, 326.6, 327.6, 328.6, 329.6)], gap=0.0)
        # shunt
        cnt[f'SW shunt {l}'] = put(SW, grid(342.1, 343.9, 0.9, sy - 2.7, sy + 2.7, 0.9))
        cnt[f'PH shunt {l}'] = put(PH, grid(356.6, 357.6, 1.0, sy - 2.7, sy + 2.7, 0.9), gap=0.15)
    # electrolytic capacitors
    for n in (2, 3, 4):
        for c in (7, 9):
            for pn in (1, 2):
                x, y, net = b.pad(f'C{n}{c:02d}', pn)
                cnt[f'C{n}{c:02d}.{pn}'] = put(net, grid(304.0, 305.1, 1.1, y - 1.5, y + 1.5, 1.0),
                                               clr=0.5 if net == '+BATT' else 0.3)
    # battery / ground terminal and connector supply pins
    put('+BATT', [(296.5, 107.0), (297.5, 107.0)])
    put('GNDPWR', [(296.5, 97.1), (297.5, 97.1)])
    # stitching of the analog ground islands to the inner plane
    put('GND', [(346.4, 61.0), (357.0, 61.0), (346.4, 81.5), (352.5, 81.5), (346.4, 91.0), (357.5, 93.0),
                (353.5, 86.5), (346.4, 107.0), (352.6, 113.5), (358.0, 116.5), (346.4, 115.0), (346.2, 85.6)],
        d=0.6, drill=0.3)
    return cnt
