"""Live MuJoCo samples using the same exported balance actor as the Pi."""
import json
import math
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / 'models/policies/balance_lqr_ppo'


def samples(seed=1000, realtime=True, policy_path=POLICY):
    from .env import FurutaEnv
    from .policy import Policy

    actor = Policy(policy_path)
    env = FurutaEnv(actor.meta['config'])
    try:
        obs, _ = env.reset(seed=seed, options={'balance': True})
        start = time.monotonic()
        while True:
            before = time.monotonic()
            action = actor.predict(obs)
            inference_ms = (time.monotonic() - before) * 1000
            used_obs = obs.tolist()
            obs, reward, terminated, truncated, info = env.step(action)
            theta, alpha, arm_speed, pend_speed = info['state']
            now = env.steps * env.dt
            yield {
                't_s': now, 'seq': env.steps, 'arm_deg': math.degrees(theta),
                'pendulum_deg': math.degrees(math.atan2(math.sin(alpha), math.cos(alpha))),
                'arm_rad_s': arm_speed, 'pendulum_rad_s': pend_speed,
                'observation': used_obs, 'action': float(action[0]),
                'requested_nm': float(action[0]) * env.c['torque_nm'],
                'applied_nm': info['torque_nm'], 'inference_ms': inference_ms,
                'simulation_step_ms': (time.monotonic() - before) * 1000,
                'cycle_ms': env.dt * 1000, 'reward': reward,
                'reward_terms': info['terms'], 'fault': info['failure_reasons'] or None,
                'qpos': env.data.qpos.tolist(), 'qvel': env.data.qvel.tolist(),
                'qacc': env.data.qacc.tolist(),
                'actuator_force_nm': float(env.data.qfrc_actuator[env.vids[0]]),
                'command_sent': False, 'policy_sha256': actor.meta['sha256'],
                'done': bool(terminated or truncated or info['fault']),
            }
            if terminated or truncated or info['fault']:
                break
            if realtime:
                time.sleep(max(0, start + now - time.monotonic()))
    finally:
        env.close()


def decode_sample(line):
    """Ignore shell messages and accept finite telemetry samples only."""
    try:
        row = json.loads(line)
        if not isinstance(row, dict):
            return None
        for key in ('t_s', 'arm_deg', 'pendulum_deg'):
            if not math.isfinite(row[key]):
                return None
    except (ValueError, TypeError, KeyError):
        return None
    return row
