import sys
XML=sys.argv[1]; sys.argv=['x', XML, '/dev/null']
exec(open('motor_sweep.py').read().split("if __name__")[0])
m=load(); K=lqr(m)
for tau in (0.02,0.025,0.03,0.04,0.05,0.07):
    r=run(m,tau,K,sgn=-1,T=20); print(tau,{k:(round(v,3) if isinstance(v,float) else v) for k,v in r.items()},flush=True)
