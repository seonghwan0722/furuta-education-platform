"""Train and evaluate a swing-up actor with a frozen balance policy."""
import argparse
import itertools
import json
import platform
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import gymnasium as gym
import mujoco
import numpy as np
import stable_baselines3
import torch
from stable_baselines3 import PPO
from stable_baselines3.common.logger import configure

from furuta_platform.common import SOURCE, config
from furuta_platform.env import FurutaEnv
from furuta_platform.history import TrainingHistory, identity, write_json
from furuta_platform.swingup import CAPTURE, EnergyTeacher, in_capture, upright_error

PARAMS = (7000, 20, 1.5, 19)


class HandoffEnv(gym.Wrapper):
    def __init__(self, env, balance):
        super().__init__(env)
        self.balance = balance

    def reset(self, **kwargs):
        self.handoff = False
        self.obs, info = self.env.reset(**kwargs)
        return self.obs, info

    def step(self, action):
        switch = not self.handoff and in_capture(self.env.state())
        self.handoff |= switch
        if self.handoff:
            action = self.balance.predict(self.obs, deterministic=True)[0]
        self.obs, reward, terminated, truncated, info = self.env.step(action)
        arm_speed = abs(info['state'][2])
        if not info['fault'] and not self.handoff:
            reward -= .15 * np.clip((arm_speed - 12) / 8, 0, 1)**2
        return self.obs, float(reward + (3 if switch and not info['fault'] else 0)), terminated, truncated, info


def rollout(env, seed, actor=None, initial=None, collect=False):
    obs, _ = env.reset(seed=seed, options={'balance':False})
    if initial is not None:
        raw = env.unwrapped
        raw.data.qpos[raw.qids] = initial[:2] + [0, raw.up]
        raw.data.qvel[raw.vids] = initial[2:]
        mujoco.mj_forward(raw.model, raw.data)
        obs = env.obs = raw.obs()
        env.handoff = True
    teacher = EnergyTeacher(env.unwrapped, *PARAMS)
    hold = best = 0
    captured = None
    examples = []
    max_arm_speed = 0.
    while True:
        if env.handoff:
            action = np.zeros(1, dtype=np.float32)
        else:
            target = teacher.action()
            action = target if actor is None else actor.predict(obs, deterministic=True)[0]
            if not in_capture(env.unwrapped.state()):
                examples.append((obs.copy(), target))
        obs, _, terminated, truncated, info = env.step(action)
        _, angle, td, ad = info['state']
        max_arm_speed = max(max_arm_speed, abs(td))
        if env.handoff and captured is None:
            captured = env.unwrapped.steps * env.unwrapped.dt
        hold = hold + 1 if env.handoff and abs(upright_error(angle)) < .174533 and abs(ad) < 1 and not info['fault'] else 0
        best = max(hold, best)
        if terminated or truncated or info['fault']:
            break
    result = {'seed':seed,'handoff_s':captured,'hold_s':best*env.unwrapped.dt,
              'success':best*env.unwrapped.dt >= 2 and not info['fault'],
              'fault':info['failure_reasons'],'peak_arm_speed':max_arm_speed}
    return result, examples if collect else []


def evaluate(env, actor=None):
    return [rollout(env, seed, actor)[0] for seed in range(1000,1020)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True)
    parser.add_argument('--balance', default='runs/balance_lqr_ppo_s42')
    parser.add_argument('--steps', type=int, default=8192)
    args = parser.parse_args()
    if args.steps < 1:
        parser.error('--steps must be positive')
    torch.set_num_threads(1)
    root = Path(args.run)
    balance_path = Path(args.balance)/'policy.zip'
    balance_id = identity(balance_path)
    balance = PPO.load(balance_path, device='cpu')
    c = config(ROOT/'configs/rev5_shaped_swingup.json')
    c['ppo'] = {'log_std_init':-4.5, 'learning_rate':0.00003}
    c['handoff'] = {'capture_abs':CAPTURE.tolist(),'balance_policy':balance_id,
                    'teacher_parameters':list(PARAMS),'entry_bonus':3,'arm_speed_penalty':.15}
    root.mkdir(parents=True, exist_ok=False)
    env = HandoffEnv(FurutaEnv(c), balance)
    corners = []
    for signs in itertools.product((-1,1), repeat=4):
        state = np.array(signs)*CAPTURE
        result,_ = rollout(env, 42, initial=state)
        corners.append({'state':state.tolist(),**result})
    teacher_eval = evaluate(env)
    write_json(root/'teacher_evaluation.json', {'capture':corners,'episodes':teacher_eval})
    print('teacher',sum(row['success'] for row in teacher_eval),flush=True)
    examples = []
    for seed in range(50):
        result, samples = rollout(env, seed, collect=True)
        if result['success']:
            examples.extend(samples)
    if not examples:
        raise RuntimeError('No successful training demonstrations')
    initial_count = len(examples)
    np.savez_compressed(root/'demonstrations.npz', observations=np.stack([x[0] for x in examples]), actions=np.stack([x[1] for x in examples]))
    model = PPO('MlpPolicy',env,seed=42,device='cpu',n_steps=256,batch_size=64,
                learning_rate=c['ppo']['learning_rate'],policy_kwargs={'activation_fn':torch.nn.Tanh,'log_std_init':-4.5})
    rng = np.random.default_rng(42)
    policy = model.policy
    optimizer = torch.optim.Adam(list(policy.mlp_extractor.policy_net.parameters())+list(policy.action_net.parameters()),lr=.001)

    def prepare(directory):
        directory.mkdir()
        write_json(directory/'config.json',c)
        (directory/'source.xml').write_bytes(SOURCE.read_bytes())
        write_json(directory/'versions.json',{'python':platform.python_version(),'torch':torch.__version__,
                   'mujoco':mujoco.__version__,'sb3':stable_baselines3.__version__,'gymnasium':gym.__version__})

    initial = root/'imitation'
    prepare(initial)
    history = TrainingHistory(initial,c,model,0,note='Energy teacher imitation with corrective teacher labels')
    try:
        for round_number in range(5):
            if round_number:
                for seed in range(100+round_number*10,110+round_number*10):
                    _, samples = rollout(env, seed, model, collect=True)
                    examples.extend(samples)
            obs = torch.tensor(np.stack([x[0] for x in examples]))
            target = torch.tensor(np.stack([x[1] for x in examples]))
            for _ in range(1800 if not round_number else 1000):
                indices = rng.integers(len(obs),size=256)
                predicted = policy.action_net(policy.mlp_extractor.forward_actor(obs[indices]))
                loss = (predicted-target[indices]).square().mean()
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
            print('imitation round',round_number,'samples',len(examples),flush=True)
        np.savez_compressed(root/'imitation_dataset.npz', observations=np.stack([x[0] for x in examples]), actions=np.stack([x[1] for x in examples]))
        write_json(initial/'imitation.json',{'successful_demo_samples':initial_count,'total_samples':len(examples),
                   'supervised_updates':5800,'teacher_parameters':list(PARAMS),'dataset':'../imitation_dataset.npz'})
        model.save(initial/'policy.zip')
        history.save_receipt(initial/'policy.zip',model,'final')
        history.finish(model,'completed')
    except BaseException as exc:
        history.finish(model,'failed',str(exc))
        raise
    imitation_eval = evaluate(env, model)
    write_json(initial/'evaluation.json',{'policy':identity(initial/'policy.zip'),'episodes':imitation_eval})
    print('imitation',sum(row['success'] for row in imitation_eval),flush=True)

    refined = root/'ppo'
    prepare(refined)
    model = PPO.load(initial/'policy.zip',env=env,device='cpu')
    history = TrainingHistory(refined,c,model,args.steps,parent=initial,note='Swing-up PPO refinement with frozen balance handoff')
    try:
        model.set_logger(configure(str(refined),['csv']))
        model.learn(total_timesteps=args.steps)
        model.save(refined/'policy.zip')
        history.save_receipt(refined/'policy.zip',model,'final')
        history.finish(model,'completed')
    except BaseException as exc:
        history.finish(model,'failed',str(exc))
        raise
    refined_eval = evaluate(env, model)
    write_json(refined/'evaluation.json',{'policy':identity(refined/'policy.zip'),'episodes':refined_eval})
    print('ppo',sum(row['success'] for row in refined_eval),flush=True)
    env.close()


if __name__ == '__main__':
    main()
