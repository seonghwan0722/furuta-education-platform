import sys, json
XML=sys.argv[1]; sys.argv=['x', XML, '/dev/null']
exec(open('motor_sweep.py').read().split("if __name__")[0])
out=[]
def rec(m,K,umax,x0,T=3.0):
    d=mujoco.MjData(m); d.qpos[:]=[0,math.pi+x0[0]]; d.qvel[:]=[0,x0[1]]
    pk=0;pw=0
    for i in range(int(T/m.opt.timestep)):
        th,al=d.qpos; thd,ald=d.qvel
        u=float(-(K@np.array([th,wrap(al-math.pi),thd,ald]))[0]); pk=max(pk,abs(u))
        d.ctrl[0]=max(-umax,min(umax,u)); mujoco.mj_step(m,d); pw=max(pw,abs(d.qvel[0]))
        if abs(wrap(d.qpos[1]-math.pi))>1.0: return False,pk,pw
    return abs(wrap(d.qpos[1]-math.pi))<0.05,pk,pw
for a in (0.0,1e-3,1e-2):
  m=load(a); K=lqr(m)
  for lab,x0 in (('5deg',(math.radians(5),0)),('10deg',(math.radians(10),0)),('15deg',(math.radians(15),0)),('tap 2rad/s',(0,2.0)),('tap 4rad/s',(0,4.0))):
    _,pk,pw=rec(m,K,50,x0)
    mn=None
    for t in (0.005,0.01,0.015,0.02,0.025,0.03,0.04,0.05,0.07,0.1,0.15,0.2,0.3,0.5,1.0):
        if rec(m,K,t,x0)[0]: mn=t;break
    row=dict(armature=a,case=lab,peak_u_unsat=round(pk,4),peak_w=round(pw,2),min_tau=mn); out.append(row); print(row)
json.dump(out,open('balance.json','w'),indent=1)
