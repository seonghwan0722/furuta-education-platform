"""MATLAB-trained PPO/SAC swing-up policies as plain numpy (no MATLAB, no torch).

Network : obs(5) / sc -> tanh(W1 . + b1) -> tanh(W2 . + b2) -> tanh(W3 . + b3)  = u in [-1, 1]
          sc = [1, 1, pi, 10, 10]; SAC policies are the deterministic mean tanh(mu).
Command : current = u * 1.5 A, rounded to 0.01 A (RMD 0xA1 LSB), clamped to +/-1.5 A; torque = 2.1 N m/A * current.
Rate    : 100 Hz (Ts = 10 ms). The policies were trained with a 10-20 ms command delay.

Observation (built by PiObserver, identical to MATLAB furuta_pi_decode / sp_env2):
  [cos(phi_m), sin(phi_m), wrap(theta_m), theta_dot_f, phi_dot_f]
  phi   = pendulum angle from UPRIGHT (0 = up, +-pi = hanging), 12-bit AS5600 quantization
  theta = arm angle (0.01 deg quantization), wrapped to (-pi, pi]
  rates = finite difference of the measured angles, first-order filter tau = 30 ms
Sign convention (MATLAB/Pi): +torque -> phi_ddot < 0 near upright. MuJoCo rev11: phi = -(alpha_mj - pi).

    from policy_np import MatlabPolicyNP, PiObserver
    pol = MatlabPolicyNP("policies/sac24_ck0100.npz"); obs = PiObserver()
    obs.reset(theta, phi)                    # once, at rest
    every 10 ms: o = obs.update(theta, phi); current_A = pol.current(o)
"""
import math
import numpy as np


def _wrap(a):
    return math.atan2(math.sin(a), math.cos(a))


class MatlabPolicyNP:
    def __init__(self, path):
        w = np.load(path)
        self.W1, self.b1, self.W2, self.b2, self.W3, self.b3 = (w[k].astype(np.float32) for k in ("W1", "b1", "W2", "b2", "W3", "b3"))
        self.sc = w["sc"].astype(np.float32)

    def __call__(self, o):
        z = np.asarray(o, np.float32) / self.sc
        h = np.tanh(self.W1 @ z + self.b1); h = np.tanh(self.W2 @ h + self.b2)
        return float(np.tanh(self.W3 @ h + self.b3)[0])

    def current(self, o, max_a=1.5):
        return max(-max_a, min(max_a, round(self(o) * 1.5 / 0.01) * 0.01))


class PiObserver:
    def __init__(self, Ts=0.01, tau=0.03):
        self.Ts, self.k = Ts, Ts / (tau + Ts)

    @staticmethod
    def measure(theta, phi):
        ma = round(math.degrees(theta) * 100) / 100 * math.pi / 180
        mp = _wrap((round(phi / (2 * math.pi) * 4096) % 4096) * 2 * math.pi / 4096)
        return ma, mp

    def reset(self, theta, phi, theta_dot=0.0, phi_dot=0.0):
        self.prev = self.measure(theta, phi); self.filt = [theta_dot, phi_dot]

    def update(self, theta, phi):
        ma, mp = self.measure(theta, phi)
        d = [(ma - self.prev[0]) / self.Ts, _wrap(mp - self.prev[1]) / self.Ts]
        self.filt = [f + self.k * (di - f) for f, di in zip(self.filt, d)]
        self.prev = (ma, mp)
        return [math.cos(mp), math.sin(mp), _wrap(ma), self.filt[0], self.filt[1]]
