"""rev11 (rev5-shape one-piece bent arm-pendulum, printed solid) STEP -> simplified MuJoCo model.
Three rigid bodies: base (fixed), arm (hinge about z), pendulum = bent printed rod (hinge along +x through z = 18 mm).
The CAD has the pendulum leg lying along -y; it is rotated +90 deg about the pivot axis so that angle 0 = hanging down.
Mass/COM/inertia are computed from the STEP solids x material density (not from the visual meshes)."""
import pickle, json, math, os, re, sys, tempfile
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from OCP.BRepTools import BRepTools
from OCP.TopoDS import TopoDS_Shape
from OCP.BRep import BRep_Builder
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_FACE
from OCP.BRep import BRep_Tool
from OCP.TopLoc import TopLoc_Location
from OCP.TopoDS import TopoDS
OUT = sys.argv[1] if len(sys.argv) > 1 else '/home/claude/mj11/out'
os.makedirs(OUT + '/meshes', exist_ok=True)
ARM_DEG = 0.0; PIVOT_Z = 18.0                            # mm, 688ZZ_A/B centres at (+-16, 0, 18)
RX = np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]], float)     # +90 deg about x: CAD leg (-y) -> hanging (-z)
U = np.array([math.cos(math.radians(ARM_DEG)), math.sin(math.radians(ARM_DEG)), 0.0])
BEARING_CATALOG_G = 3.6                                   # 688ZZ catalogue mass; CAD is a solid ring (5.9 g)
rows = pickle.load(open('/home/claude/mj11/rows.pkl', 'rb'))
ser = {r[1]: r for r in pickle.load(open('/home/claude/mj11/parts.pkl', 'rb'))}
for r in rows:
    if r['name'].startswith('688ZZ'):
        k = BEARING_CATALOG_G / r['m']; r['m'] *= k; r['Ic'] = (np.array(r['Ic'])*k).tolist(); r['mat'] = 'steel (688ZZ catalogue mass)'
TIP = ('M6x30_button_bolt_weight',)
PIV = np.array([0, 0, PIVOT_Z])
for r in rows:
    if r['group'] == 'pend':
        r['C'] = (PIV + RX @ (np.array(r['C']) - PIV)).tolist(); r['Ic'] = (RX @ np.array(r['Ic']) @ RX.T).tolist()
def combine(rs, about=None):
    m = sum(r['m'] for r in rs); C = sum(np.array(r['C'])*r['m'] for r in rs)/m
    ref = C if about is None else np.array(about)
    I = np.zeros((3, 3))
    for r in rs:
        d = np.array(r['C']) - ref
        I += np.array(r['Ic']) + r['m']*(np.dot(d, d)*np.eye(3) - np.outer(d, d))
    return m, C, I
def shape(s):
    fn = tempfile.mktemp(suffix='.brep'); open(fn, 'wb').write(s)
    sh = TopoDS_Shape(); BRepTools.Read_s(sh, fn, BRep_Builder()); os.remove(fn); return sh
def tess(sh, tol=0.25, ang=0.45):
    BRepMesh_IncrementalMesh(sh, tol, False, ang, True)
    V, F = [], []
    ex = TopExp_Explorer(sh, TopAbs_FACE)
    while ex.More():
        f = TopoDS.Face_s(ex.Current()); loc = TopLoc_Location()
        tri = BRep_Tool.Triangulation_s(f, loc)
        if tri is not None:
            T = loc.Transformation(); off = len(V)
            for i in range(1, tri.NbNodes()+1):
                p = tri.Node(i).Transformed(T); V.append((p.X(), p.Y(), p.Z()))
            rev = f.Orientation() == 1
            for i in range(1, tri.NbTriangles()+1):
                a, b, c = tri.Triangle(i).Get()
                F.append((off+a-1, off+c-1, off+b-1) if rev else (off+a-1, off+b-1, off+c-1))
        ex.Next()
    return np.array(V), np.array(F, dtype=np.int64)
def write_stl(fn, V, F):
    tri = V[F]; n = np.cross(tri[:, 1]-tri[:, 0], tri[:, 2]-tri[:, 0]); n /= (np.linalg.norm(n, axis=1)[:, None] + 1e-12)
    rec = np.zeros(len(F), dtype=[('n', '<f4', 3), ('v', '<f4', (3, 3)), ('a', '<u2')])
    rec['n'] = n; rec['v'] = tri
    with open(fn, 'wb') as f:
        f.write(b'furuta rev11 bent simplified'.ljust(80, b' ')); f.write(np.uint32(len(F)).tobytes()); f.write(rec.tobytes())
COL = {'print': (0.82, 0.83, 0.85, 1), 'metal': (0.74, 0.76, 0.79, 1), 'screw_silver': (0.78, 0.79, 0.82, 1), 'screw_black': (0.08, 0.08, 0.09, 1),
       'brass': (0.80, 0.60, 0.22, 1), 'magnet': (0.40, 0.10, 0.30, 1), 'motor': (0.15, 0.15, 0.17, 1), 'cable': (0.75, 0.10, 0.10, 1),
       'dark': (0.12, 0.12, 0.14, 1), 'other': (0.6, 0.6, 0.62, 1)}
def vis_key(r):
    v = r['vis']
    if r['group'] == 'pend' and r['name'].startswith(TIP):
        return 'tip_' + v, COL.get(v, COL['other'])
    if v == 'logo':
        return ('logo_blue', (0.10, 0.35, 0.80, 1)) if 'blue' in r['name'] else ('logo_black', (0.10, 0.10, 0.11, 1))
    if v in ('pcb', 'logo', 'other') and r['rgb']:
        c = tuple(round(x, 2) for x in r['rgb']); return '%s_%02x%02x%02x' % (v, int(c[0]*255), int(c[1]*255), int(c[2]*255)), (*c, 1)
    return v, COL.get(v, COL['other'])
# ---------------------------------------------------------------- meshes per (body, visual class)
geoms = {'base': [], 'arm': [], 'pend': []}
BASE_ZMIN = 1e9
tri_count = 0
for g in geoms:
    buckets = {}
    for r in [x for x in rows if x['group'] == g]:
        k, col = vis_key(r)
        V, F = tess(shape(ser[r['path']][2]), *((0.6, 0.8) if r['vis'] == 'motor' and g == 'base' else (0.25, 0.45)))
        if len(F) == 0: continue
        V = V.copy()
        if g == 'pend': V = (V - PIV) @ RX.T
        V *= 1e-3
        if g == 'base': BASE_ZMIN = min(BASE_ZMIN, V[:, 2].min()*1e3)
        b = buckets.setdefault(k, [[], [], col, 0, []])
        F2 = F + b[3]; b[0].append(V); b[1].append(F2); b[3] += len(V); b[4].append(r['name'])
    for k, (Vs, Fs, col, _, names) in buckets.items():
        V = np.vstack(Vs); F = np.vstack(Fs); tri_count += len(F)
        fn = '%s_%s.stl' % (g, k); write_stl(os.path.join(OUT, 'meshes', fn), V, F)
        geoms[g].append((fn, col, names, 'tip' if k.startswith('tip_') else ''))
# tip weight parts get their own geoms so the no-weight variant can drop them
print('triangles', tri_count)
FLOOR = BASE_ZMIN*1e-3
# ---------------------------------------------------------------- inertial
mp = {}
arm_rows = [r for r in rows if r['group'] == 'arm']
m, C, I = combine(arm_rows); mp['arm'] = dict(m=m, C=C, I=I)
for variant, prs in (('with_tip', [r for r in rows if r['group'] == 'pend']),
                     ('no_tip', [r for r in rows if r['group'] == 'pend' and not r['name'].startswith(TIP)])):
    m, C, I = combine(prs); mp['pend_' + variant] = dict(m=m, C=C, I=I)
def fullinertia(I):  # g mm^2 -> kg m^2, order ixx iyy izz ixy ixz iyz
    I = I*1e-9; return '%.6e %.6e %.6e %.6e %.6e %.6e' % (I[0, 0], I[1, 1], I[2, 2], I[0, 1], I[0, 2], I[1, 2])
def vec(v, s=1e-3): return ' '.join('%.6f' % (x*s) for x in v)
def cam(name, az, el, dist, t):
    d = np.array([math.cos(math.radians(az))*math.cos(math.radians(el)), math.sin(math.radians(az))*math.cos(math.radians(el)), math.sin(math.radians(el))])
    p = np.array(t) + dist*d; f = -d; x = np.cross(f, [0, 0, 1]); x /= np.linalg.norm(x); y = np.cross(x, f)
    return '<camera name="%s" pos="%.4f %.4f %.4f" xyaxes="%.4f %.4f %.4f %.4f %.4f %.4f"/>' % (name, *p, *x, *y)
CAM_ISO = cam('iso', -58, 24, 0.72, (0.02, 0, -0.08)); CAM_FRONT = cam('front', -90, 4, 0.72, (0.02, 0, -0.08)); CAM_HEAD = cam('head', -62, 28, 0.30, (0.035, 0, 0.0))
def mjcf(variant):
    P = mp['pend_' + variant]; A = mp['arm']
    pc = P['C'] - np.array([0, 0, PIVOT_Z])
    L = []
    w = L.append
    w('<mujoco model="furuta_rev11_bent_%s">' % variant)
    w('  <!-- generated by build_rev11.py from 4_Archives/rev5-rev11_old/Furuta_rev11_STEP/Furuta_Pendulum_rev11_full.step; units m, kg, s -->')
    w('  <compiler angle="radian" meshdir="meshes" inertiafromgeom="false" autolimits="true"/>')
    w('  <option timestep="0.001" integrator="RK4" gravity="0 0 -9.81"/>')
    w('  <visual><headlight ambient="0.22 0.22 0.22" diffuse="0.35 0.35 0.35" specular="0.05 0.05 0.05"/><global offwidth="2000" offheight="1500"/>'
      '<quality shadowsize="4096"/></visual>')
    w('  <default>')
    w('    <geom contype="0" conaffinity="0" group="1" density="0"/>')
    w('    <default class="arm_joint"><joint damping="1e-4" frictionloss="0.012" armature="0"/></default>')
    w('    <default class="pend_joint"><joint damping="1e-5" frictionloss="2e-4" armature="0"/></default>')
    w('  </default>')
    w('  <asset>')
    for g in geoms:
        for fn, col, names, tag in geoms[g]:
            if variant == 'no_tip' and tag == 'tip': continue
            w('    <mesh name="%s" file="%s"/>' % (fn[:-4], fn))
    w('    <texture name="sky" type="skybox" builtin="gradient" rgb1="1 1 1" rgb2="0.92 0.93 0.95" width="256" height="256"/>')
    w('    <texture name="grid" type="2d" builtin="checker" rgb1="0.94 0.94 0.94" rgb2="0.88 0.88 0.88" width="512" height="512"/>')
    w('    <material name="floor" texture="grid" texrepeat="8 8"/>')
    w('  </asset>')
    w('  <worldbody>')
    w('    <light pos="0.3 -0.3 0.8" dir="-0.3 0.3 -0.8" diffuse="0.45 0.45 0.45"/>')
    w('    <light pos="-0.4 -0.2 0.5" dir="0.4 0.2 -0.5" diffuse="0.18 0.18 0.18" castshadow="false"/>')
    w('    <geom name="floor" type="plane" size="0.4 0.4 0.01" pos="0 0 %.4f" material="floor"' % FLOOR + ' group="0"/>')
    w('    '+CAM_ISO)
    w('    '+CAM_FRONT)
    w('    '+CAM_HEAD)
    w('    <!-- base: tower D100, top plate, RMD-X6 (whole), slip ring + bracket, electronics box (fixed) -->')
    for fn, col, names, tag in geoms['base']:
        w('    <geom type="mesh" mesh="%s" rgba="%.3f %.3f %.3f 1"/>' % (fn[:-4], *col[:3]))
    w('    <body name="arm" pos="0 0 0">')
    w('      <!-- rotating head: hub + drive tube, arm holder, 688ZZ x2, encoder pod + cover, AS5600 board -->')
    w('      <inertial pos="%s" mass="%.6f" fullinertia="%s"/>' % (vec(A['C']), A['m']*1e-3, fullinertia(A['I'])))
    w('      <joint name="arm" class="arm_joint" type="hinge" axis="0 0 1"/>')
    for fn, col, names, tag in geoms['arm']:
        w('      <geom type="mesh" mesh="%s" rgba="%.3f %.3f %.3f 1"/>' % (fn[:-4], *col[:3]))
    w('      <site name="encoder_chip" pos="-0.0277 0 0.0180" size="0.001"/>')
    w('      <body name="pendulum" pos="0 0 %.6f">' % (PIVOT_Z*1e-3))
    w('        <!-- one-piece bent PLA Tough+ arm-pendulum (rev5 shape, 100%% infill) + magnet cap%s; angle 0 = hanging down -->' % (' + M6x30 bolt weight' if variant == 'with_tip' else ''))
    w('        <inertial pos="%s" mass="%.6f" fullinertia="%s"/>' % (vec(pc), P['m']*1e-3, fullinertia(P['I'])))
    w('        <joint name="pendulum" class="pend_joint" type="hinge" axis="%.6f %.6f 0"/>' % (U[0], U[1]))
    for fn, col, names, tag in geoms['pend']:
        if variant == 'no_tip' and tag == 'tip': continue
        w('        <geom type="mesh" mesh="%s" rgba="%.3f %.3f %.3f 1"/>' % (fn[:-4], *col[:3]))
    tip = RX @ (np.array([76.0, -143.3, 18.0]) - PIV) * 1e-3
    w('        <site name="tip" pos="%s" size="0.002"/>' % ' '.join('%.5f' % x for x in tip))
    w('      </body>')
    w('    </body>')
    w('  </worldbody>')
    w('  <actuator>')
    w('    <!-- arm torque (N m). RMD-X6-P20 can do far more; keep this clamp for training safety and widen deliberately -->')
    w('    <motor name="arm_torque" joint="arm" gear="1" ctrlrange="-1 1"/>')
    w('  </actuator>')
    w('  <sensor>')
    w('    <jointpos name="arm_angle" joint="arm"/><jointpos name="pend_angle" joint="pendulum"/>')
    w('    <jointvel name="arm_vel" joint="arm"/><jointvel name="pend_vel" joint="pendulum"/>')
    w('    <actuatorfrc name="arm_torque_applied" actuator="arm_torque"/>')
    w('  </sensor>')
    w('  <keyframe>')
    w('    <key name="down" qpos="0 0"/>')
    w('    <key name="up" qpos="0 3.14159265"/>')
    w('  </keyframe>')
    w('</mujoco>')
    open(os.path.join(OUT, 'furuta_rev11_bent_%s.xml' % variant), 'w').write('\n'.join(L) + '\n')
mjcf('with_tip'); mjcf('no_tip')
def j(x): return np.asarray(x).tolist()
json.dump({k: dict(mass_kg=v['m']*1e-3, com_m=j(v['C']*1e-3), inertia_about_com_kgm2=j(v['I']*1e-9)) for k, v in mp.items()} |
          {'pivot_m': [0, 0, PIVOT_Z*1e-3], 'pend_axis': j(U), 'parts': [dict(name=r['name'], body=r['group'], material=r['mat'], mass_g=round(r['m'], 3)) for r in rows]},
          open(os.path.join(OUT, 'massprops.json'), 'w'), indent=1, ensure_ascii=False)
for k, v in mp.items(): print(k, 'mass %.1f g' % v['m'], 'COM mm', np.round(v['C'], 2))
