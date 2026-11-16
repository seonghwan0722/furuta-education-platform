"""Nominal Furuta swing-up teacher and balance handoff."""
import math

import mujoco
import numpy as np


def upright_error(angle):
    return math.atan2(math.sin(angle), math.cos(angle))


CAPTURE = np.array([1., .16, 4., 2.])


def in_capture(state):
    theta, alpha, arm_speed, pend_speed = state
    return bool(np.all(np.abs([theta, upright_error(alpha), arm_speed, pend_speed]) <= CAPTURE))


class EnergyTeacher:
    def __init__(self, env, energy_gain, center_gain, brake_gain, speed_cap):
        self.env = env
        self.energy_gain = energy_gain
        self.center_gain = center_gain
        self.brake_gain = brake_gain
        self.speed_cap = speed_cap
        self.mass = np.zeros((env.model.nv, env.model.nv))
        body = env.model.jnt_bodyid[env.jids[1]]
        mujoco.mj_forward(env.model, env.data)
        delta = env.data.subtree_com[body] - env.data.xanchor[env.jids[1]]
        self.height_energy = env.model.body_subtreemass[body] * abs(env.model.opt.gravity[2]) * np.linalg.norm(delta[1:])

    def action(self):
        env = self.env
        mujoco.mj_forward(env.model, env.data)
        mujoco.mj_fullM(env.model, env.data, self.mass)
        theta, alpha, td, ad = env.state()
        arm, pend = env.vids
        inertia = self.mass[pend, pend]
        coupling = self.mass[arm, pend] / inertia
        energy_deficit = self.height_energy * (1 - math.cos(alpha)) - .5 * inertia * ad**2
        # Use the arm acceleration's contribution to pendulum energy change.
        acceleration = -self.energy_gain * energy_deficit * ad * coupling
        if abs(ad) < .05 and math.cos(alpha) < -.95:
            acceleration += 35 * (1 if alpha <= math.pi else -1)
        acceleration -= self.center_gain * theta + self.brake_gain * td
        acceleration = np.clip(acceleration, (-self.speed_cap - td)/env.dt, (self.speed_cap - td)/env.dt)
        bias = env.data.qfrc_bias - env.data.qfrc_passive
        torque = (self.mass[arm, arm] - coupling*self.mass[arm, pend])*acceleration + bias[arm] - coupling*bias[pend]
        return np.array([np.clip(torque/env.c['torque_nm'], -1., 1.)], dtype=np.float32)

