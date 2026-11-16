"""Imitate a local MuJoCo LQR controller before PPO fine-tuning."""
import mujoco
import numpy as np
import torch

from .common import observe


def initialize_from_lqr(model, env, seed):
    if any(env.c['randomization'].values()):
        raise ValueError('LQR initialization requires a nominal simulation')
    data = mujoco.MjData(env.model)

    def transition(state, action):
        mujoco.mj_resetData(env.model, data)
        data.qpos[env.qids] = state[:2] + [0, env.up]
        data.qvel[env.vids] = state[2:]
        data.ctrl[0] = action * env.c['torque_nm']
        for _ in range(env.c['frame_skip']):
            mujoco.mj_step(env.model, data)
        return np.r_[data.qpos[env.qids] - [0, env.up], data.qvel[env.vids]]

    epsilon = 1e-5
    zero = np.zeros(4)
    a = np.column_stack([
        (transition(delta, 0) - transition(-delta, 0)) / (2 * epsilon)
        for delta in np.eye(4) * epsilon
    ])
    b = ((transition(zero, epsilon) - transition(zero, -epsilon)) / (2 * epsilon))[:, None]
    q = np.diag([.1, 30., .02, .2])
    p = q.copy()
    for _ in range(10000):
        gain = np.linalg.solve(np.eye(1) + b.T @ p @ b, b.T @ p @ a)
        updated = q + a.T @ p @ (a - b @ gain)
        if np.max(np.abs(updated - p)) < 1e-9:
            break
        p = updated
    else:
        raise ValueError('LQR Riccati iteration did not converge')
    if np.max(np.abs(np.linalg.eigvals(a - b @ gain))) >= 1:
        raise ValueError('LQR linearization is not stabilized')

    rng = np.random.default_rng(seed)
    ranges = np.array([.15, .12, .8, .8])

    def dataset(size):
        states = rng.uniform(-ranges, ranges, size=(size, 4))
        inputs = [observe(*state, env.c) for state in states]
        targets = np.clip(-states @ gain.T, -1, 1)
        return torch.tensor(np.array(inputs), dtype=torch.float32), torch.tensor(targets, dtype=torch.float32)

    inputs, targets = dataset(8192)
    validation, expected = dataset(1024)
    policy = model.policy
    optimizer = torch.optim.Adam(
        list(policy.mlp_extractor.policy_net.parameters()) + list(policy.action_net.parameters()),
        lr=0.001,
    )

    def action(obs):
        return policy.action_net(policy.mlp_extractor.forward_actor(obs))

    prior_threads = torch.get_num_threads()
    try:
        torch.set_num_threads(1)
        for _ in range(1500):
            indices = rng.integers(len(inputs), size=256)
            loss = (action(inputs[indices]) - targets[indices]).square().mean()
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
        with torch.no_grad():
            rmse = (action(validation).clamp(-1, 1) - expected).square().mean().sqrt().item()
    finally:
        torch.set_num_threads(prior_threads)
    return {
        'method': 'MuJoCo finite-difference discrete LQR imitation',
        'gain': gain.tolist(),
        'state_ranges': ranges.tolist(),
        'samples': len(inputs),
        'validation_samples': len(validation),
        'optimizer_steps': 1500,
        'validation_action_rmse': rmse,
    }
