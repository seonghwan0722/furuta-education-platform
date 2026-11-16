import argparse,copy,csv,hashlib,json,platform
from pathlib import Path
import numpy as np
from .common import config,SOURCE
from .history import TrainingHistory,identity

def main():
    p=argparse.ArgumentParser(); p.add_argument('command',choices=['inspect','train','evaluate','export']); p.add_argument('--config'); p.add_argument('--run',default='runs/rev5'); p.add_argument('--steps',type=int); p.add_argument('--episodes',type=int,default=20); p.add_argument('--render',action='store_true')
    p.add_argument('--seed',type=int); p.add_argument('--initialize-from',help='Previous run directory for staged training')
    p.add_argument('--eval-start',choices=['swingup','balance'],default='swingup')
    p.add_argument('--checkpoint',help='Checkpoint filename within the run checkpoints folder, for evaluation')
    p.add_argument('--note',default='',help='Purpose or changes for this training run')
    p.add_argument('--checkpoint-every',type=int,default=10000)
    p.add_argument('--lqr-warm-start',action='store_true',help='Initialize a new actor by imitating local LQR')
    a=p.parse_args()
    if a.checkpoint and (a.command!='evaluate' or Path(a.checkpoint).name!=a.checkpoint or not a.checkpoint.endswith('.zip')):
        p.error('--checkpoint requires evaluate and a ZIP filename within checkpoints')
    if a.lqr_warm_start and (a.command!='train' or a.initialize_from): p.error('--lqr-warm-start requires a new training run')
    if a.checkpoint_every<1 or (a.steps is not None and (a.steps<0 or (a.steps==0 and not a.lqr_warm_start))): p.error('Use positive steps, or zero with --lqr-warm-start')
    from .env import FurutaEnv
    from stable_baselines3 import PPO
    from stable_baselines3.common.monitor import Monitor
    from stable_baselines3.common.callbacks import BaseCallback
    from stable_baselines3.common.env_checker import check_env
    from stable_baselines3.common.logger import configure
    import mujoco,torch,gymnasium,stable_baselines3
    out=Path(a.run)
    if a.command=='train' or a.command=='inspect': c=config(a.config)
    else: c=json.loads((out/'config.json').read_text(encoding='utf-8-sig'))
    if a.seed is not None: c['seed']=a.seed
    if a.command in ('evaluate','export') and (out/'source.xml').read_bytes()!=SOURCE.read_bytes():
        raise ValueError('Source MJCF changed since training; restore snapshot before evaluation/export')
    if a.episodes<1: raise ValueError('episodes must be positive')
    if a.command=='inspect':
        original=mujoco.MjModel.from_xml_path(str(SOURCE))
        print('original loaded nq,nv,nu:',original.nq,original.nv,original.nu)
    env=FurutaEnv(c)
    if a.command=='inspect':
        check_env(env); print('nq,nv,nu',env.model.nq,env.model.nv,env.model.nu,'up raw rad',env.up)
        print('mass',env.model.body_mass,'inertia',env.model.body_inertia); env.close(); return
    if a.command=='train':
        steps=c['total_steps'] if a.steps is None else a.steps
        if a.lqr_warm_start:
            from .lqr import initialize_from_lqr
            c['actor_initialization']='lqr_imitation'
        if out.exists(): raise FileExistsError('Use a new --run directory to preserve previous experiments')
        out.mkdir(parents=True)
        (out/'config.json').write_text(json.dumps(c,indent=2))
        (out/'source.xml').write_bytes(SOURCE.read_bytes())
        (out/'versions.json').write_text(json.dumps({'python':platform.python_version(),'mujoco':mujoco.__version__,'gymnasium':gymnasium.__version__,'sb3':stable_baselines3.__version__,'torch':torch.__version__}))
        env=Monitor(env,str(out/'monitor.csv'))
        if a.initialize_from:
            parent=Path(a.initialize_from)
            identity(parent/'policy.zip')
            if (parent/'source.xml').read_bytes()!=SOURCE.read_bytes(): raise ValueError('Parent model source mismatch')
            old=config(parent/'config.json')
            if any(old[k]!=c[k] for k in ('physics_dt','frame_skip','torque_nm','velocity_scale')): raise ValueError('Parent I/O/action timing mismatch')
            model=PPO.load(parent/'policy.zip',env=env,device='cpu'); model.set_random_seed(c['seed'])
            (out/'parent.json').write_text(json.dumps({'run':str(parent.resolve()),'policy_sha256':hashlib.sha256((parent/'policy.zip').read_bytes()).hexdigest()},indent=2))
        else:
            model=PPO('MlpPolicy',env,seed=c['seed'],device='cpu',n_steps=256,batch_size=64,policy_kwargs={'activation_fn':torch.nn.Tanh, 'log_std_init':c.get('ppo',{}).get('log_std_init',0.0)},verbose=1)
        history=TrainingHistory(out,c,model,steps,note=a.note,parent=a.initialize_from,checkpoint_every=a.checkpoint_every)
        class RecordedCheckpoint(BaseCallback):
            def _on_step(self):
                if self.n_calls%max(a.checkpoint_every//self.model.n_envs,1)==0:
                    path=out/'checkpoints'/f'policy_{self.num_timesteps}_steps.zip'
                    path.parent.mkdir(parents=True,exist_ok=True)
                    self.model.save(path); history.save_receipt(path,self.model,'checkpoint')
                return True
        class RewardLog(BaseCallback):
            def _on_step(self):
                for info in self.locals['infos']:
                    for key,value in info.get('terms',{}).items(): self.logger.record_mean('reward_terms/'+key,value)
                    self.logger.record_mean('safety/fault_fraction',float(info.get('fault',False)))
                return True
        model.set_logger(configure(str(out),['stdout','csv']))
        try:
            if a.lqr_warm_start:
                imitation=initialize_from_lqr(model,env.unwrapped,c['seed'])
                (out/'lqr_imitation.json').write_text(json.dumps(imitation,indent=2))
            if steps:
                model.learn(total_timesteps=steps,callback=[RecordedCheckpoint(),RewardLog()])
            model.save(out/'policy'); history.save_receipt(out/'policy.zip',model,'final')
            history.finish(model,'completed')
        except BaseException as error:
            history.finish(model,'interrupted' if isinstance(error,KeyboardInterrupt) else 'failed',str(error))
            raise
        finally: env.close()
        return
    policy_path=out/'checkpoints'/a.checkpoint if a.checkpoint else out/'policy.zip'
    policy_identity=identity(policy_path)
    model=PPO.load(policy_path,device='cpu')
    if a.command=='export':
        from .policy import Policy
        layers=[m for m in model.policy.mlp_extractor.policy_net if isinstance(m,torch.nn.Linear)]+[model.policy.action_net]
        if any(not isinstance(m,(torch.nn.Linear,torch.nn.Tanh)) for m in model.policy.mlp_extractor.policy_net): raise ValueError('unsupported activation')
        dest=out/'export'; dest.mkdir(exist_ok=True)
        weights={}
        for i,l in enumerate(layers): weights[f'w{i}']=l.weight.detach().cpu().numpy(); weights[f'b{i}']=l.bias.detach().cpu().numpy()
        np.savez(dest/'actor.npz',**weights)
        meta={'schema':'furuta-io-v1','layers':len(layers),'sha256':hashlib.sha256((dest/'actor.npz').read_bytes()).hexdigest(),'config':c,'upright_raw_rad':env.up,'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'normalization':'fixed velocity scales; no running statistics','hardware_approved':False}
        meta['training_policy']=policy_identity
        meta['training_record']=None
        if policy_identity['provenance']=='recorded':
            record=json.loads((out/'training.json').read_text(encoding='utf-8'))
            if record['training_id']!=policy_identity['training_id']: raise ValueError('Training record ID mismatch')
            meta['training_record']=record
        (dest/'manifest.json').write_text(json.dumps(meta,indent=2))
        actor=Policy(dest); rng=np.random.default_rng(0)
        for obs in rng.uniform(-1,1,(100,6)).astype(np.float32): np.testing.assert_allclose(actor.predict(obs),model.predict(obs,deterministic=True)[0],atol=1e-5)
        print('export parity passed: 100 observations'); env.close(); return
    # Nominal deterministic evaluation: randomization explicitly disabled, fixed seed sequence.
    env.close(); c=copy.deepcopy(c)
    c['randomization']={k:0 for k in c['randomization']}; env=FurutaEnv(c)
    rows=[]
    for episode in range(a.episodes):
        obs,_=env.reset(seed=c['seed']+episode,options={'balance':a.eval_start=='balance'}); hold=best=0.; arrival=None; errors=[]; inputs=[]; ret=0; totals={}
        while True:
            action,_=model.predict(obs,deterministic=True); obs,r,term,trunc,info=env.step(action); ret+=r
            for key,value in info['terms'].items(): totals[key]=totals.get(key,0.)+value
            error=abs(np.arctan2(np.sin(info['state'][1]),np.cos(info['state'][1])))
            ok=not info['fault'] and error<c['success']['angle_rad'] and abs(info['state'][3])<c['success']['velocity_rad_s']
            hold=hold+env.dt if ok else 0.; best=max(best,hold)
            if ok and arrival is None: arrival=env.steps*env.dt
            errors.append(error); inputs.append(info['torque_nm'])
            if a.render:
                import PIL.Image
                PIL.Image.fromarray(env.render()).save(out/'latest_frame.png')
            if term or trunc or info['fault']: break
        rows.append({'seed':c['seed']+episode,'success':best>=c['success']['hold_seconds'],'first_entry_s':arrival,'longest_hold_s':best,'closest_upright_deg':float(np.degrees(min(errors))),'angle_rmse_rad':float(np.sqrt(np.mean(np.square(errors)))),'torque_rms_nm':float(np.sqrt(np.mean(np.square(inputs)))),'torque_peak_nm':float(max(abs(x) for x in inputs)),'return_until_stop':ret,'reward_terms_until_stop':totals,'duration_s':env.steps*env.dt,'fault':info['fault'],'failure_reasons':info['failure_reasons']})
    name='evaluation.json' if a.eval_start=='swingup' else 'evaluation_balance.json'
    if a.checkpoint:
        name=f'evaluation_{a.eval_start}_{policy_path.stem}.json'
    (out/name).write_text(json.dumps({'mode':'nominal deterministic, proposed criteria; physical rollout stops at first fault','training_policy':policy_identity,'start':a.eval_start,'success_rate':sum(x['success'] for x in rows)/len(rows),'episodes':rows},indent=2)); env.close()
if __name__=='__main__': main()
