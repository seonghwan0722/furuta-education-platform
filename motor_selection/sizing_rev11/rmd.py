import sys, json
XML=sys.argv[1]; sys.argv=['x', XML, '/dev/null']
exec(open('motor_sweep.py').read().split("if __name__")[0])
out=[]
for a,fs in ((0.0,1),(0.0,2),(2.5e-2,1),(2.5e-2,8)):
  m=load(a,fs); K=lqr(m)
  for tau in ((0.03,0.04,0.05,0.07,0.1,0.15,0.2) if a==0 else (0.1,0.2,0.3,0.5,1.0,2.0,4.0)):
    r=run(m,tau,K,sgn=-1,T=20); r.update(armature=a,fric=fs,tau=tau); out.append(r)
    print({k:(round(v,3) if isinstance(v,float) else v) for k,v in r.items()},flush=True)
json.dump(out,open('energy_sweep.json','w'),indent=1)
