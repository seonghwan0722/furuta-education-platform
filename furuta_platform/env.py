import math
import numpy as np
import gymnasium as gym
from gymnasium import spaces
import mujoco
from .common import ARM,PEND,config,model_xml,observe,validate
from .rewards import reward_terms
class FurutaEnv(gym.Env):
    metadata={'render_modes':['rgb_array'],'render_fps':100}
    def __init__(self,c=None,render_mode=None):
        self.c=c or config(); self.render_mode=render_mode; self.renderer=None
        validate(self.c)
        self.model=mujoco.MjModel.from_xml_string(model_xml(self.c)); self.data=mujoco.MjData(self.model)
        self.jids=[mujoco.mj_name2id(self.model,mujoco.mjtObj.mjOBJ_JOINT,n) for n in (ARM,PEND)]
        self.qids=self.model.jnt_qposadr[self.jids]; self.vids=self.model.jnt_dofadr[self.jids]
        self.mass=self.model.body_mass.copy(); self.inertia=self.model.body_inertia.copy(); self.damping=self.model.dof_damping.copy()
        # Aggregate CAD pendulum subtree COM at q=0. Rotation about +x maximizes height at atan2(y,z).
        mujoco.mj_forward(self.model,self.data)
        b=self.model.jnt_bodyid[self.jids[1]]
        delta=self.data.subtree_com[b]-self.data.xanchor[self.jids[1]]
        self.up=math.atan2(delta[1],delta[2]); self.dt=self.c['physics_dt']*self.c['frame_skip']
        self.action_space=spaces.Box(-1,1,(1,),np.float32); self.observation_space=spaces.Box(-1,1,(6,),np.float32)
    def state(self):
        t,p=self.data.qpos[self.qids]; td,pd=self.data.qvel[self.vids]
        return float(t),float(p-self.up),float(td),float(pd)
    def obs(self):
        s=np.array(self.state()); s+=self.np_random.normal(0,self.c['randomization']['noise_std'],4)
        return np.array(observe(*s,self.c),np.float32)
    def reset(self,seed=None,options=None):
        super().reset(seed=seed); mujoco.mj_resetData(self.model,self.data)
        r=self.c['randomization']
        for a,base,k in [(self.model.body_mass,self.mass,'mass_fraction'),(self.model.body_inertia,self.inertia,'inertia_fraction'),(self.model.dof_damping,self.damping,'damping_fraction')]:
            f=r[k]
            if not 0<=f<1: raise ValueError(k)
            # global scale preserves inertia triangle inequalities
            a[:]=base*self.np_random.uniform(1-f,1+f)
        mujoco.mj_setConst(self.model,self.data)
        init=self.c.get('initialization',{})
        balance=(options or {}).get('balance')
        if balance is None: balance=self.np_random.random()<init.get('balance_probability',0.) if init else False
        noise=init.get('angle_noise_rad',.03)
        self.data.qpos[self.qids]=[0,self.up+(0 if balance else math.pi)]
        self.data.qpos[self.qids]+=self.np_random.uniform(-noise,noise,2)
        self.data.qvel[:]=0; self.steps=0; self.torque=0.; self.queue=[0.]*int(r['delay_steps'])
        self.previous_action=0.; self.failed=False; self.failure_reasons=[]; self.last_state=None
        mujoco.mj_forward(self.model,self.data)
        self.last_obs=self.obs()
        self.last_state=list(self.state())
        return self.last_obs.copy(),{'start':'balance' if balance else 'swingup'}
    def step(self,action):
        a=np.asarray(action)
        if a.shape!=(1,) or not np.isfinite(a).all(): raise ValueError('invalid action')
        u=float(np.clip(a[0],-1,1)); self.queue.append(u*self.c['torque_nm']); target=self.queue.pop(0)
        if self.failed:
            self.steps+=1; self.data.ctrl[:]=0; self.torque=0.
            terms={'failure':self.c['failure']['reward_per_step']}
            return self.last_obs.copy(),sum(terms.values()),False,self.steps*self.dt>=self.c['episode_seconds'],{'terms':terms,'state':self.last_state,'torque_nm':0.,'fault':True,'absorbing':True,'failure_reasons':self.failure_reasons}
        tau=self.c['randomization']['motor_time_constant']
        for _ in range(self.c['frame_skip']):
            self.torque+=(target-self.torque)*(1 if tau<=0 else -math.expm1(-self.c['physics_dt']/tau))
            self.data.ctrl[0]=self.torque; mujoco.mj_step(self.model,self.data)
        applied_torque=self.torque
        self.steps+=1; state=self.state(); t,p,td,pd=state
        lim=self.c['limits']
        reasons=[]
        if not np.isfinite(self.data.qpos).all() or not np.isfinite(self.data.qvel).all(): reasons.append('nonfinite_state')
        if abs(t)>lim['arm_rad']: reasons.append('arm_position')
        if abs(td)>lim['velocity'][0]: reasons.append('arm_velocity')
        if abs(pd)>lim['velocity'][1]: reasons.append('pend_velocity')
        fault=bool(reasons); absorbing=fault and self.c.get('failure',{}).get('mode')=='absorbing'
        if absorbing:
            self.failed=True; self.failure_reasons=reasons
            self.data.ctrl[:]=0; self.torque=0.
            terms={'failure':self.c['failure']['reward_per_step']}
        else:
            terms=reward_terms(state,u,self.previous_action,self.c)
        self.previous_action=u
        if np.isfinite(state).all(): self.last_state=list(state); self.last_obs=self.obs()
        return self.last_obs.copy(),sum(terms.values()),fault and not absorbing,self.steps*self.dt>=self.c['episode_seconds'],{'terms':terms,'state':self.last_state,'torque_nm':applied_torque,'fault':fault,'absorbing':absorbing,'failure_reasons':reasons}
    def render(self):
        if self.renderer is None: self.renderer=mujoco.Renderer(self.model,480,640)
        self.renderer.update_scene(self.data); return self.renderer.render()
    def close(self):
        if self.renderer: self.renderer.close()
