"""Replay-only Pi inference/communication reference. Never opens motor/serial device."""
import argparse,json,math,sys,time
from pathlib import Path
from furuta_platform.common import observe
class Guard:
    def __init__(self,c,timeout):
        if timeout<=0: raise ValueError('timeout must be positive')
        self.c=c; self.timeout=timeout; self.seq=-1; self.sensor_time=-1; self.latched=False
    def command(self,packet,now,actor):
        try:
            if self.latched: raise ValueError('fault latched; operator reset required')
            if packet['schema']!='furuta-io-v1' or packet['status']!='ok': raise ValueError('sensor status')
            if type(packet['seq']) is not int or packet['seq']<=self.seq: raise ValueError('sequence')
            # t_pi_s is MCU sample timestamp translated to Pi monotonic clock by measured synchronization.
            ts=packet['t_pi_s']
            if not math.isfinite(ts) or not 0<=now-ts<=self.timeout or ts<=self.sensor_time: raise ValueError('stale/out-of-order sensor')
            s=packet['state']; lim=self.c['limits']
            if len(s)!=4 or not all(math.isfinite(v) for v in s): raise ValueError('sensor values')
            if abs(s[0])>lim['arm_rad'] or abs(s[2])>lim['velocity'][0] or abs(s[3])>lim['velocity'][1]: raise ValueError('motion limit')
            a=float(actor.predict(observe(*s,self.c))[0])
            if not math.isfinite(a) or abs(a)>1: raise ValueError('inference')
            self.seq=packet['seq']; self.sensor_time=ts
            return {'schema':'furuta-io-v1','seq':self.seq,'sample_t_pi_s':ts,'torque_nm':a*self.c['torque_nm'],'enable':False,'mode':'replay_only'}
        except Exception as e:
            self.latched=True
            return {'schema':'furuta-io-v1','torque_nm':0.,'enable':False,'fault':str(e)}
def main():
    from furuta_platform.policy import Policy
    p=argparse.ArgumentParser(); p.add_argument('policy'); p.add_argument('records'); p.add_argument('--timeout',type=float,required=True,help='Measured freshness budget seconds'); a=p.parse_args()
    actor=Policy(a.policy); guard=Guard(actor.meta['config'],a.timeout)
    with open(a.records,encoding='utf-8-sig') as f:
        for line in f:
            try:
                row=json.loads(line); result=guard.command(row['packet'],row['receive_t_pi_s'],actor)
            except Exception as e:
                guard.latched=True; result={'torque_nm':0,'enable':False,'fault':str(e)}
            print(json.dumps(result))
if __name__=='__main__': main()
