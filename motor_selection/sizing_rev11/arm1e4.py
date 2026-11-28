import sys
XML=sys.argv[1]; sys.argv=['x', XML, '/dev/null']
exec(open('motor_sweep.py').read().split("if __name__")[0])
for a in (5e-5,1e-4):
  m=load(a); K=lqr(m)
  for tau in (0.08,0.15,0.3):
    r=run(m,tau,K,sgn=-1,T=20); print(a,tau,{k:(round(v,3) if isinstance(v,float) else v) for k,v in r.items()},flush=True)
