import json, math, pathlib, xml.etree.ElementTree as ET
ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = ROOT/'models/rev5/source/furuta_rev5_lite_mujoco.xml'
ARM='base_link_J1_yaw'
PEND='688ZZ_B_J2_pendulum'
def config(path=None):
    c=json.loads(pathlib.Path(path or ROOT/'configs/rev5_baseline.json').read_text(encoding='utf-8-sig'))
    validate(c)
    return c
def validate(c):
    log_std_init=c.get('ppo',{}).get('log_std_init',0.0)
    if not math.isfinite(log_std_init) or not -10<=log_std_init<=2:
        raise ValueError('ppo.log_std_init must be finite and between -10 and 2')
    version=c.get('reward_version','baseline')
    if version not in ('baseline','shaped_v1'): raise ValueError('reward_version')
    init=c.get('initialization',{})
    if not 0<=init.get('balance_probability',0)<=1: raise ValueError('balance_probability')
    noise=init.get('angle_noise_rad',.03)
    if not math.isfinite(noise) or noise<0: raise ValueError('angle_noise_rad')
    if version=='shaped_v1':
        w=c['reward']; shape=c['reward_shape']
        for key in ('upright','balance','arm_boundary','effort','smoothness'): w[key]
        if not 0<=shape['arm_edge_fraction']<1: raise ValueError('arm_edge_fraction')
        if not math.isfinite(shape['upright_power']) or shape['upright_power']<=0: raise ValueError('upright_power')
        if len(shape['balance_velocity_scale'])!=2 or any(not math.isfinite(v) or v<=0 for v in shape['balance_velocity_scale']): raise ValueError('balance_velocity_scale')
        failure=c['failure']
        lower_bound=-w['arm_boundary']-w['effort']-4*w['smoothness']
        if failure['mode']!='absorbing' or not math.isfinite(failure['reward_per_step']) or failure['reward_per_step']>lower_bound:
            raise ValueError('Failure reward must not exceed the lower bound of any active reward')
    for k in ('physics_dt','torque_nm','episode_seconds'):
        if not math.isfinite(c[k]) or c[k]<=0: raise ValueError(k)
    if type(c['frame_skip']) is not int or c['frame_skip']<1: raise ValueError('frame_skip')
    for x in c['velocity_scale']+c['limits']['velocity']+[c['limits']['arm_rad']]:
        if not math.isfinite(x) or x<=0: raise ValueError('limits/scales')
    for x in c['damping']+list(c['reward'].values()):
        if not math.isfinite(x) or x<0: raise ValueError('damping/reward')
    r=c['randomization']
    for k in ('mass_fraction','inertia_fraction','damping_fraction'):
        if not 0<=r[k]<1: raise ValueError(k)
    if type(r['delay_steps']) is not int or r['delay_steps']<0: raise ValueError('delay_steps')
    for k in ('noise_std','motor_time_constant'):
        if not math.isfinite(r[k]) or r[k]<0: raise ValueError(k)
def model_xml(c):
    tree=ET.parse(SOURCE); r=tree.getroot()
    for mesh in r.findall('asset/mesh'):
        mesh.set('file',str(SOURCE.parent/mesh.get('file')))
    op=ET.SubElement(r,'option',timestep=str(c['physics_dt']),integrator='implicitfast',solver='Newton',gravity='0 0 -9.81')
    ET.SubElement(op,'flag',contact='disable')
    # Visual CAD geometry is deliberately not a collision model.
    for j in r.iter('joint'):
        j.set('damping',str(c['damping'][0 if j.get('name')==ARM else 1])); j.set('limited','false')
    ac=ET.SubElement(r,'actuator'); t=str(c['torque_nm'])
    ET.SubElement(ac,'motor',name='arm_torque',joint=ARM,gear='1',ctrllimited='true',ctrlrange=f'-{t} {t}',forcelimited='true',forcerange=f'-{t} {t}')
    return ET.tostring(r,encoding='unicode')
def observe(theta,alpha,td,ad,c):
    vals=[theta,alpha,td,ad]
    if not all(math.isfinite(float(x)) for x in vals): raise ValueError('nonfinite sensor')
    v=c['velocity_scale']
    return [math.sin(theta),math.cos(theta),math.sin(alpha),math.cos(alpha),max(-1,min(1,td/v[0])),max(-1,min(1,ad/v[1]))]
