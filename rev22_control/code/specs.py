import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from evalrun import *
def specs():
    S = {}
    D = design(REV11_ID, Q=(10, 10, 1, 1), qObs=(200, 800)); S['rev11', 'LQR'] = dict(D=D, g=dict(mode='lqr'))
    Db = design(BASELINE, qObs=(200, 800)); Kb = -Db['K'][0]
    S['rev11', 'PID'] = dict(D=Db, g=dict(mode='pid', kE=400, pid=[0.75 * Kb[1], 0.75 * Kb[3], 0.75 * Kb[0], 0.75 * Kb[2], 0.5]))
    D = design(REV11_ID, Q=(3, 10, 5, 5), qObs=(50, 200)); S['rev11', 'LMPC'] = dict(D=D, g=dict(mode='lmpc', slewBal=0.3))
    D = design(REV22, Q=(10, 10, 1, 1), qObs=(200, 800)); K = -D['K'][0]; S['rev22', 'LQR'] = dict(D=D, g=dict(mode='lqr'))
    S['rev22', 'PID'] = dict(D=D, g=dict(mode='pid', pid=[0.75 * K[1], 0.75 * K[3], 0.75 * K[0], 0.75 * K[2], 0.5]))
    D = design(REV22, Q=(3, 10, 5, 5), qObs=(50, 200)); S['rev22', 'LMPC'] = dict(D=D, g=dict(mode='lmpc', slewBal=0.3))
    return S
