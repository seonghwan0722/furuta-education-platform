import sys, json
XML=sys.argv[1]; sys.argv=['x', XML, '/dev/null']
exec(open('motor_sweep.py').read().split("if __name__")[0])
out={}
A=6.1e-6
for fs in (1,2):
  m=load(A,fs); K=lqr(m)
  for tau in (0.08,0.15,0.29,0.46):
    r=run(m,tau,K,sgn=-1,T=20); r.update(fric=fs,tau=tau); out[f'{fs}_{tau}']=r
    print({k:(round(v,3) if isinstance(v,float) else v) for k,v in r.items()},flush=True)
# balance tap 4 rad/s & 15 deg at tau 0.15
m=load(A); K=lqr(m)
def rec(umax,x0,T=3.0):
    d=mujoco.MjData(m); d.qpos[:]=[0,math.pi+x0[0]]; d.qvel[:]=[0,x0[1]]; pw=0
    for i in range(int(T/m.opt.timestep)):
        th,al=d.qpos; thd,ald=d.qvel
        u=float(-(K@np.array([th,wrap(al-math.pi),thd,ald]))[0]); d.ctrl[0]=max(-umax,min(umax,u)); mujoco.mj_step(m,d); pw=max(pw,abs(d.qvel[0]))
        if abs(wrap(d.qpos[1]-math.pi))>1.0: return False,pw
    return abs(wrap(d.qpos[1]-math.pi))<0.05,pw
for lab,x0 in (('15deg',(math.radians(15),0)),('tap4',(0,4.0)),('tap6',(0,6.0)),('25deg',(math.radians(25),0))):
    print('bal',lab,rec(0.15,x0))
json.dump(out,open('gl35.json','w'),indent=1)
