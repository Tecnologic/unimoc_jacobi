"""Split the combined PCB into the two boards and write JLCPCB production data.

    python3 scripts/layout/export.py      (from the repository root, needs KiCad 10)

Output: production/jlcpcb/<board>/ with Gerber and drill files, a zip of them and
the placement file. The intermediate single-board PCB files are not kept.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

import pcbnew

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SPLIT_X = pcbnew.FromMM(274.0)       # logic board left, power board right
LAYERS = 'F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts'


def split(keep_power, path):
    b = pcbnew.LoadBoard(os.path.join(ROOT, 'jacobi.kicad_pcb'))

    def other(x):
        return (x < SPLIT_X) if keep_power else (x >= SPLIT_X)

    kill = []
    for f in b.GetFootprints():
        xs = [p.GetPosition().x for p in f.Pads()] or [f.GetPosition().x]
        if other(sum(xs) // len(xs)):
            kill.append(f)
    kill += [t for t in b.GetTracks() if other(t.GetPosition().x)]
    kill += [z for z in b.Zones() if other(z.GetBoundingBox().GetCenter().x)]
    kill += [d for d in b.GetDrawings() if other(d.GetBoundingBox().GetCenter().x)]
    for item in kill:
        b.Delete(item)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pcbnew.SaveBoard(path, b)


def run(*a):
    subprocess.run(a, check=True, stdout=subprocess.DEVNULL)


def main():
    out = os.path.join(ROOT, 'production', 'jlcpcb')
    for name, power in (('logic', False), ('power', True)):
        d = os.path.join(out, name)
        shutil.rmtree(d, ignore_errors=True)
        os.makedirs(d)
        with tempfile.TemporaryDirectory() as tmp:
            pcb = os.path.join(tmp, f'jacobi_{name}.kicad_pcb')
            shutil.copy(os.path.join(ROOT, 'jacobi.kicad_pro'), os.path.join(tmp, f'jacobi_{name}.kicad_pro'))
            split(power, pcb)
            g = os.path.join(d, 'gerber')
            os.makedirs(g)
            run('kicad-cli', 'pcb', 'export', 'gerbers', '--layers', LAYERS, '--subtract-soldermask',
                '--no-protel-ext', '-o', g + '/', pcb)
            run('kicad-cli', 'pcb', 'export', 'drill', '--format', 'excellon', '--excellon-separate-th',
                '--generate-map', '--map-format', 'gerberx2', '-o', g + '/', pcb)
            run('kicad-cli', 'pcb', 'export', 'pos', '--format', 'csv', '--units', 'mm', '--side', 'both',
                '-o', os.path.join(d, f'jacobi_{name}_cpl.csv'), pcb)
        with zipfile.ZipFile(os.path.join(d, f'jacobi_{name}_gerber.zip'), 'w', zipfile.ZIP_DEFLATED) as z:
            for fn in sorted(os.listdir(g)):
                z.write(os.path.join(g, fn), fn)
        shutil.rmtree(g)
        print(name, sorted(os.listdir(d)))


if __name__ == '__main__':
    sys.exit(main())
