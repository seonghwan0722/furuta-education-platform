"""Train a bounded PPO correction to nominal energy swing-up."""
import argparse
import json
from pathlib import Path
import platform

import mujoco
import numpy as np
import stable_baselines3
import torch
from stable_baselines3 import PPO
from stable_baselines3.common.logger import configure

import train_swingup as experiment
from furuta_platform.common import SOURCE, config
from furuta_platform.env import FurutaEnv
from furuta_platform.history import TrainingHistory, identity, sha256, write_json
from furuta_platform.swingup import CAPTURE, EnergyTeacher, in_capture


class LQRBalance:
    def __init__(self, gain, velocity_scale):
        self.gain = np.asarray(gain)
        self.velocity_scale = np.asarray(velocity_scale)

    def predict(self, obs, deterministic=True):
        theta_sin, theta_cos, alpha_sin, alpha_cos, *velocity = obs
        state = np.r_[np.arctan2(theta_sin, theta_cos),
                      np.arctan2(alpha_sin, alpha_cos),
                      self.velocity_scale * velocity]
        return np.clip(-self.gain @ state, -1, 1).astype(np.float32), None


class ResidualEnv(experiment.HandoffEnv):
    def reset(self, **kwargs):
        result = super().reset(**kwargs)
        parameters = self.unwrapped.c['residual']['teacher_parameters']
        self.teacher = EnergyTeacher(self.unwrapped, *parameters)
        return result

    def step(self, action):
        if not self.handoff and not self.unwrapped.failed and not in_capture(self.unwrapped.state()):
            action = np.clip(self.teacher.action() + self.unwrapped.c['residual']['action_scale'] * action, -1, 1)
        return super().step(action)


class ZeroCorrection:
    def predict(self, obs, deterministic=True):
        return np.zeros(1, dtype=np.float32), None


def evaluate(env, actor, seeds):
    rows = [experiment.rollout(env, seed, actor)[0] for seed in seeds]
    return {'episodes': rows, 'successes':sum(row['success'] for row in rows),
            'faults':sum(bool(row['fault']) for row in rows),
            'handoffs':sum(row['handoff_s'] is not None for row in rows)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True)
    parser.add_argument('--steps', type=int, default=8192)
    parser.add_argument('--scale', type=float, default=.02)
    parser.add_argument('--evaluate-only', action='store_true')
    args = parser.parse_args()
    if args.steps < 1 or not 0 < args.scale <= .1:
        parser.error('Use positive steps and a correction scale in (0, .1]')
    torch.set_num_threads(1)
    root = Path(args.run)
    if args.evaluate_only:
        c = config(root/'config.json')
        if (root/'source.xml').read_bytes() != SOURCE.read_bytes():
            raise ValueError('Simulation XML differs from the saved run')
        if c['residual']['capture_abs'] != CAPTURE.tolist():
            raise ValueError('Handoff thresholds differ from the saved run')
        path = root/'policy.zip'
        identity(path)
        env = ResidualEnv(FurutaEnv(c), LQRBalance(c['residual']['balance_gain'],c['velocity_scale']))
        try:
            model = PPO.load(path, device='cpu')
            for first_seed in (1000, 2000):
                result = evaluate(env, model, range(first_seed,first_seed+20))
                print(f"Seeds {first_seed}-{first_seed+19}: {result['successes']}/20 successes, {result['faults']} faults")
        finally:
            env.close()
        return
    root.mkdir(parents=True, exist_ok=False)
    c = config(experiment.ROOT/'configs/rev5_shaped_swingup.json')
    gain_path = experiment.ROOT/'runs/balance_lqr_init_s42/lqr_imitation.json'
    gain = json.loads(gain_path.read_text(encoding='utf-8'))['gain']
    c['residual'] = {'action_scale':args.scale, 'teacher_parameters':list(experiment.PARAMS),
                     'balance_gain':gain, 'balance_gain_source_sha256':sha256(gain_path),
                     'capture_abs':CAPTURE.tolist(), 'learning_rate':.00003}
    write_json(root/'config.json',c)
    (root/'source.xml').write_bytes(SOURCE.read_bytes())
    write_json(root/'versions.json',{'python':platform.python_version(),'torch':torch.__version__,
               'mujoco':mujoco.__version__,'sb3':stable_baselines3.__version__})
    for runner in (Path(__file__), Path(experiment.__file__)):
        (root/(runner.name+'.snapshot')).write_bytes(runner.read_bytes())
    env = ResidualEnv(FurutaEnv(c), LQRBalance(gain,c['velocity_scale']))
    baseline = evaluate(env, ZeroCorrection(), range(1000,1020))
    write_json(root/'baseline_evaluation.json',baseline)
    print('zero correction',baseline['successes'],flush=True)
    model = PPO('MlpPolicy',env,seed=c['seed'],device='cpu',n_steps=256,batch_size=64,
                learning_rate=c['residual']['learning_rate'],
                policy_kwargs={'activation_fn':torch.nn.Tanh,'log_std_init':-3.5})
    with torch.no_grad():
        model.policy.action_net.weight.zero_()
        model.policy.action_net.bias.zero_()
    history = TrainingHistory(root,c,model,args.steps,note='PPO residual on energy swing-up with local LQR balance')
    try:
        model.set_logger(configure(str(root),['csv']))
        model.learn(total_timesteps=args.steps)
        model.save(root/'policy.zip')
        history.save_receipt(root/'policy.zip',model,'final')
        history.finish(model,'completed')
    except BaseException as exc:
        history.finish(model,'failed',str(exc))
        raise
    for name, seeds in [('evaluation',range(1000,1020)),('evaluation_holdout',range(2000,2020))]:
        result=evaluate(env,model,seeds)
        result['policy']=identity(root/'policy.zip')
        write_json(root/(name+'.json'),result)
        print(name,result['successes'],result['faults'],flush=True)
    env.close()


if __name__ == '__main__':
    main()
