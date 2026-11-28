import sys, json
XML=sys.argv[1]; sys.argv=['x', XML, '/dev/null']
exec(open('motor_sweep.py').read().split("if __name__")[0])
out=[]
for fs in (1,8):
  m=load(2.5e-2,fs); K=lqr(m)
  for tau in (0.5,1.0,2.0,4.0):
    best=None
    for acc in (30,60,120,250):
      for akd in (2,5,10):
        for akp in (5,20):
          r=run(m,tau,K,sgn=-1,T=15,acc=acc,akd=akd,akp=akp,ff=0.012*fs,catch=0.3)
          if r['ok'] and (best is None or r['t_up']<best['t_up']): r.update(acc=acc,akd=akd,akp=akp); best=r
    print(fs,tau,{k:(round(v,3) if isinstance(v,float) else v) for k,v in (best or {}).items()},flush=True)
    out.append(dict(fric=fs,tau=tau,best=best))
json.dump(out,open('rmd_ct.json','w'),indent=1)
