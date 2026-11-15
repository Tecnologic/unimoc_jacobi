"""Silkscreen clean-up and board texts."""
import re
import pcbnew

MM = pcbnew.FromMM


def finish(B):
    b = B.b
    for f in b.GetFootprints():
        ref = f.Reference()
        ref.SetTextSize(pcbnew.VECTOR2I(MM(1.0), MM(1.0)))
        ref.SetTextThickness(MM(0.15))
        r = f.GetReference()
        # passives keep their designator on the fab layer only: the boards are too dense for it
        if re.match(r'^(R|C|FB|TH|D11|D5|N|H)\d', r):
            ref.SetVisible(False)
    for d in b.GetDrawings():
        if d.GetClass() != 'PCB_TEXT':
            continue
        power = pcbnew.ToMM(d.GetPosition().x) > 270
        if d.GetText().startswith('UNIMOC'):
            h, x, y = (1.5, 357.0, 134.5) if power else (3.0, 219.0, 134.5)
            d.SetTextSize(pcbnew.VECTOR2I(MM(h), MM(h)))
            d.SetTextThickness(MM(0.25 if power else 0.45))
        else:
            d.SetText('JACOBI rev 0.3')
            x, y = (353.0, 60.4) if power else (219.0, 131.6)
        d.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
