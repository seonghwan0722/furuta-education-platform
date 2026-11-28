"""rev22 mass properties from Furuta_rev22.step (props.json from step_props.py) -> MuJoCo XML + Furuta coefficients.
Densities are ASSUMPTIONS (STEP has no material/mass data)."""
import json, math, sys, numpy as np
P = json.load(open(sys.argv[1] if len(sys.argv) > 1 else 'props.json'))
PLA = 1.24e-3   # g/mm^3, 100% infill assumption (same as rev11 massprops)
RHO = [  # (name substring, density g/mm^3 or fixed mass g, body)
 ('rev22_pend_axle_arm_PLA', PLA, 'pend'), ('rev22_pend_rod_PLA', PLA, 'pend'),
 ('rev22_ball_knob', 1.40e-3, 'pend'), ('rev22_INS_M6', 8.5e-3, 'pend'), ('rev22_SET_M6', 7.85e-3, 'pend'),
 ('rev22_INS_M3', 8.5e-3, 'pend'), ('rev22_CSK_M3x8_corner', 7.85e-3, 'pend'),
 ('magnet_8x2', 7.5e-3, 'pend'), ('magnet_holder_Al', 2.70e-3, 'pend'), ('Ering_E6', 7.85e-3, 'pend'), ('shim_8x10', 7.85e-3, 'pend'),
 ('688ZZ', ('mass', 3.6), 'arm'),
 ('drum_rev16d', PLA, 'arm'), ('lid_rev16d', PLA, 'arm'), ('bearing_cartridge', PLA, 'arm'), ('hub_rev16g', PLA, 'arm'),
 ('slipring_drive_adapter', PLA, 'arm'),
 ('AS5600_chip', 1.4e-3, 'arm'), ('Grove_AS5600_PCB', 1.85e-3, 'arm'), ('Grove_connector', 1.4e-3, 'arm'),
 ('Grove_switch', 1.4e-3, 'arm'), ('Grove_plug', 1.4e-3, 'arm'), ('cable_AS5600', 1.9e-3, 'arm'),
 ('INS_drum', 8.5e-3, 'arm'), ('CSK_M3x8_lid_', 7.85e-3, 'arm'), ('SHCS_M3x8_cartridge', 7.85e-3, 'arm'),
 ('SHCS_M4x16_drum_hub_motor', 7.85e-3, 'arm'),
]
def classify(path):
    if 'lid_tower' in path: return None
    for key, rho, body in RHO:
        if key in path: return rho, body
    return None
bodies = {'arm': [], 'pend': []}
for e in P:
    r = classify(e['path'])
    if r is None: continue
    rho, body = r
    V = e['V']
    if isinstance(rho, tuple): m = rho[1]
    else: m = rho * V
    s = m / V
    I = np.array(e['I']) * s   # g mm^2 about own COM (OCC tensor, unit density -> scale)
    bodies[body].append(dict(name=e['path'].split('/')[-1], m=m, c=np.array(e['c']), I=I))
def combine(parts):
    M = sum(p['m'] for p in parts); C = sum(p['m'] * p['c'] for p in parts) / M
    I = np.zeros((3, 3))
    for p in parts:
        d = p['c'] - C; I += p['I'] + p['m'] * (np.dot(d, d) * np.eye(3) - np.outer(d, d))
    return M, C, I
out = {}
for b in bodies:
    M, C, I = combine(bodies[b])
    out[b] = dict(mass_kg=M / 1e3, com_m=(C / 1e3).tolist(), inertia_about_com_kgm2=(I * 1e-9).tolist(),
                  parts=[dict(name=p['name'], mass_g=round(p['m'], 3)) for p in bodies[b]])
# pendulum hinge: through motor axis point (0,0,z) along direction of ball centre in xy
ball = [e for e in P if 'ball_knob' in e['path']][0]['c']; mag = [e for e in P if 'magnet_8x2' in e['path']][0]['c']
u = np.array([ball[0], ball[1], 0.0]); u /= np.linalg.norm(u)
zpiv = mag[2] / 1e3
out['pivot_m'] = [0, 0, zpiv]; out['pend_axis'] = u.tolist()
out['ball_center_m'] = (np.array(ball) / 1e3).tolist()
out['arm_radius_ball_m'] = float(np.hypot(ball[0], ball[1]) / 1e3)
out['ball_drop_m'] = float(zpiv - ball[2] / 1e3)
out['assumptions'] = 'densities: PLA 1.24 g/cm3 (100% infill), bakelite 1.40, brass 8.5, steel 7.85, Al 2.70, NdFeB 7.5, PCB 1.85, plastic 1.4, cable 1.9; 688ZZ 3.6 g catalogue (whole bearing on arm body); motor rotor/slipring rotor not in CAD -> covered by measured armature'
json.dump(out, open('massprops_rev22.json', 'w'), indent=1)
for b in ('arm', 'pend'):
    print(b, 'mass %.2f g' % (out[b]['mass_kg'] * 1e3), 'com mm', np.round(np.array(out[b]['com_m']) * 1e3, 2))
    for p in out[b]['parts']: print('   ', p)
print('axis', u, 'pivot z', zpiv, 'arm r', out['arm_radius_ball_m'], 'drop', out['ball_drop_m'])
