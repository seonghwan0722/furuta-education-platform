import copy,math,unittest
import numpy as np
from furuta_platform.common import ROOT,config,validate
from furuta_platform.rewards import reward_terms
from furuta_platform.env import FurutaEnv
class RewardTests(unittest.TestCase):
    def setUp(self): self.c=config(ROOT/'configs/rev5_shaped_balance.json')
    def total(self,state,u=0,prev=0): return sum(reward_terms(state,u,prev,self.c).values())
    def test_upright_and_gated_speed(self):
        self.assertGreater(self.total([0,0,0,0]),self.total([0,math.pi,0,0]))
        self.assertGreater(self.total([0,0,0,0]),self.total([0,0,0,10]))
        self.assertAlmostEqual(self.total([0,math.pi,0,0]),self.total([0,math.pi,0,10]))
    def test_edge_effort_smoothness(self):
        t=reward_terms([0,0,0,0],0,0,self.c)
        edge=reward_terms([self.c['limits']['arm_rad']*.95,0,0,0],0,0,self.c)
        self.assertEqual(t['arm_boundary'],0); self.assertLess(edge['arm_boundary'],0)
        self.assertLess(self.total([0,0,0,0],1,1),self.total([0,0,0,0]))
        self.assertLess(self.total([0,0,0,0],1,-1),self.total([0,0,0,0],1,1))
    def test_failure_bound(self):
        c=copy.deepcopy(self.c); c['failure']['reward_per_step']=0
        with self.assertRaises(ValueError): validate(c)
    def test_staged_starts(self):
        for stage,bal in [('balance',True),('swingup',False)]:
            env=FurutaEnv(config(ROOT/f'configs/rev5_shaped_{stage}.json'))
            try:
                obs,info=env.reset(seed=7); alpha=env.state()[1]
                error=abs(math.atan2(math.sin(alpha),math.cos(alpha)))
                self.assertLess(error,.04) if bal else self.assertGreater(error,math.pi-.04)
                obs2,_=env.reset(seed=7); np.testing.assert_array_equal(obs,obs2)
                env.reset(seed=7,options={'balance':not bal})
                self.assertEqual(info['start'],'balance' if bal else 'swingup')
            finally: env.close()
    def test_absorbing_failure_freezes_physics_until_horizon(self):
        c=copy.deepcopy(self.c); c['episode_seconds']=.03
        env=FurutaEnv(c)
        try:
            env.reset(seed=2); env.data.qpos[env.qids[0]]=7
            obs,r,term,trunc,info=env.step(np.zeros(1))
            self.assertTrue(info['fault']); self.assertFalse(term); self.assertEqual(r,-1)
            self.assertTrue(np.isfinite(obs).all()); time=env.data.time
            _,r,term,trunc,info=env.step(np.ones(1))
            self.assertEqual(env.data.time,time); self.assertEqual(env.data.ctrl[0],0); self.assertEqual(r,-1)
            _,r,term,trunc,info=env.step(np.ones(1))
            self.assertTrue(trunc); self.assertFalse(term)
        finally: env.close()
    def test_baseline_formula_unchanged(self):
        c=config(); s=[.2,.3,.4,.5]; u=.6; w=c['reward']
        expected=math.cos(.3)-w['arm']*.2**2-w['arm_velocity']*.4**2-w['pend_velocity']*.5**2-w['effort']*.6**2
        self.assertAlmostEqual(sum(reward_terms(s,u,0,c).values()),expected)
if __name__=='__main__':unittest.main()
