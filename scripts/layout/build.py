import sys, time, json, os
S = '/tmp/claude-0/-home-user/31ebc478-6d24-506f-aca2-18b9ec9b7a7d/scratchpad'
sys.path.insert(0, S + '/tools')
from kl import Board
import power, power_route, logic
what = sys.argv[1] if len(sys.argv) > 1 else 'all'
FIRST = S + '/work/first.json'
first = json.load(open(FIRST)) if os.path.exists(FIRST) else []
for it in range(int(sys.argv[2]) if len(sys.argv) > 2 else 1):
    t = time.time()
    B = Board(S + '/work/base.kicad_pcb')
    logic.place(B)
    if what != 'place':
        power.power(B)
        R = power_route.route(B)
        print('power failed', R.failed, round(time.time() - t), 's')
        R2 = logic.route(B, first)
        print('logic failed', R2.failed, round(time.time() - t), 's', flush=True)
        new = [f[0] for f in R2.failed if f[0] not in first and f[0] not in logic.PLANES]
        if new:
            first = new + first
            json.dump(first, open(FIRST, 'w'))
        B.fill()
    B.save(S + '/work/jacobi.kicad_pcb')
    if what == 'place' or not new:
        break
