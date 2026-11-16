"""Encoder calibration and causal velocity estimator, same alpha=0 upright contract."""
import math
class Encoder:
    def __init__(self,offset,sign,tau,max_gap):
        if sign not in (-1,1) or tau<0 or max_gap<=0: raise ValueError('calibration')
        self.offset=offset; self.sign=sign; self.tau=tau; self.max_gap=max_gap; self.prev=None
    def update(self,raw_rad,t):
        if not all(math.isfinite(v) for v in (raw_rad,t)): raise ValueError('encoder nonfinite')
        angle=self.sign*(raw_rad-self.offset)
        if self.prev is None:
            self.prev=(angle,t,angle,0.); return angle,0.,False
        old,ot,unwrapped,v=self.prev; dt=t-ot
        if not 0<dt<=self.max_gap: raise ValueError('encoder sample gap')
        delta=math.atan2(math.sin(angle-old),math.cos(angle-old))
        unwrapped+=delta; gain=1 if self.tau==0 else -math.expm1(-dt/self.tau)
        v+=gain*(delta/dt-v); self.prev=(angle,t,unwrapped,v)
        return unwrapped,v,True
