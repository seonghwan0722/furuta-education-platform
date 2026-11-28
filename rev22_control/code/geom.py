import json, numpy as np, math
r22 = json.load(open('massprops_rev22.json')); r11 = json.load(open('../hp/handoff_python_20261124/rev11_model/massprops.json'))
C = json.load(open('coeffs.json'))
def frame(mp, key):
    P = mp[key]; u = np.array(mp['pend_axis']); z = np.array([0, 0, 1.]); y = np.cross(z, u)
    R = np.stack([u, y, z]); cc = R @ (np.array(P['com_m']) - np.array(mp['pivot_m'])); I = R @ np.array(P['inertia_about_com_kgm2']) @ R.T
    m = P['mass_kg']; a = cc[0]; l = math.hypot(cc[1], cc[2])
    return dict(m=m, a=a, l=l, Ixx=I[0, 0], Ixz=I[0, 2], arm_mass=mp['arm']['mass_kg'])
for nm, mp, k in (('rev11', r11, 'pend_with_tip'), ('rev22', r22, 'pend')):
    g = frame(mp, k); c = C[nm]
    print(nm, {k: round(v, 6) for k, v in g.items()}, 'T0 %.3f s' % (2 * math.pi * math.sqrt(c['beta2'] / c['delta'])),
          'mal %.3e Ixz-part %.3e' % (g['m'] * g['a'] * g['l'], c['gam'] - g['m'] * g['a'] * g['l']))
