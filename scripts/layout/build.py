import sys, json
sys.path.insert(0, '/tmp/claude-0/-home-user/31ebc478-6d24-506f-aca2-18b9ec9b7a7d/scratchpad/tools')
from kl import Board
import power
S = '/tmp/claude-0/-home-user/31ebc478-6d24-506f-aca2-18b9ec9b7a7d/scratchpad'
B = Board(S + '/work/base.kicad_pcb')
cnt = power.power(B)
print(cnt)
B.fill()
B.save(S + '/work/jacobi.kicad_pcb')
