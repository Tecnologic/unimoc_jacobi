"""Generate the PCB layout of both boards.

    python3 scripts/layout/build.py [passes]      (from the repository root)

Starts from the placed but unrouted board of commit BASE, places the parts,
draws pours, via fields and the gate drive, routes the small signals and
writes jacobi.kicad_pcb. Nets the router could not finish are put first in the
next pass (retry_first.json keeps that order). Needs the KiCad 10 Python
module pcbnew, numpy, scipy and Pillow.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
BASE = '8e1a0e9'          # last commit with the unrouted board

from kl import Board      # noqa: E402
import finish             # noqa: E402
import logic              # noqa: E402
import power              # noqa: E402
import power_route        # noqa: E402

FIRST = os.path.join(HERE, 'retry_first.json')


def main():
    passes = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    count = json.load(open(FIRST)) if os.path.exists(FIRST) else {}
    with tempfile.TemporaryDirectory() as tmp:
        base = os.path.join(tmp, 'jacobi.kicad_pcb')
        with open(base, 'wb') as f:
            f.write(subprocess.check_output(['git', '-C', ROOT, 'show', f'{BASE}:jacobi.kicad_pcb']))
        for _ in range(passes):
            t = time.time()
            B = Board(base)
            logic.place(B)
            power.power(B)
            R = power_route.route(B)
            print('power board, not routed:', R.failed, flush=True)
            # nets that failed most often go first
            first = sorted(count, key=lambda n: -count[n])
            R2 = logic.route(B, first)
            print('logic board, not routed:', R2.failed, round(time.time() - t), 's', flush=True)
            bad = {f[0] for f in R2.failed if f[0] not in logic.PLANES}
            if R2.failed or R.failed:
                for n in bad:
                    count[n] = count.get(n, 0) + 1
                json.dump(count, open(FIRST, 'w'), indent=1, sort_keys=True)
                if bad:
                    continue
            if os.environ.get('ROUTED'):          # keep the routed board to work on the silkscreen alone
                B.save(os.environ['ROUTED'])
            finish.finish(B)
            B.fill()
            out = os.path.join(tmp, 'out.kicad_pcb')      # not in ROOT: saving would rewrite jacobi.kicad_pro
            B.save(out)
            shutil.copy(out, os.path.join(ROOT, 'jacobi.kicad_pcb'))
            return 0 if not (R2.failed or R.failed) else 1
    return 1


if __name__ == '__main__':
    sys.exit(main())
