"""Numerical PID/LQR/LMPC runtime for Pendulum Studio controller exports.

No CAN, sensors, serial device, motor enable, or automatic motion is opened here.
State: [arm angle relative to captured home, wrapped upright error, arm rate,
pendulum rate], radians and rad/s. Output: normalized torque; the caller must
retain the existing real actuator/current/speed/braking restrictions.

Design source is control-core.js, rev11-control-lab-upright-v1. Exporting its
linearized design does not establish closed-loop stability on physical hardware.
"""
import copy
import json
import math
import time

import numpy as np

MAX_CONFIG_BYTES = 32768
STATE_NAMES = ['theta', 'upright_error', 'theta_dot', 'alpha_dot']
MODEL = 'rev11-control-lab-upright-v1'


class ControllerError(ValueError):
    def __init__(self, message, reason='controller'):
        super().__init__(message)
        self.reason = reason


def _reject_constant(value):
    raise ControllerError('Non-finite JSON constant: ' + value)


def _unique_object(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ControllerError('Duplicate configuration key: ' + key)
        out[key] = value
    return out


def decode_config(raw):
    """Bounded strict JSON decoding. Constructor performs semantic validation."""
    if not isinstance(raw, bytes) or not 1 <= len(raw) <= MAX_CONFIG_BYTES:
        raise ControllerError('Controller configuration must contain 1..32768 bytes')
    try:
        config = json.loads(raw.decode('utf-8'), parse_constant=_reject_constant,
                            object_pairs_hook=_unique_object)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as error:
        raise ControllerError('Invalid controller JSON: ' + str(error)) from error
    if not isinstance(config, dict):
        raise ControllerError('Controller configuration must be an object')
    return config


def _keys(value, expected, name):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise ControllerError(name + ' has missing or unsupported fields')


def _number(value, low, high, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ControllerError(name + ' must be a number')
    try:
        out = float(value)
    except (OverflowError, ValueError) as error:
        raise ControllerError(name + ' is not finite') from error
    if not math.isfinite(out) or not low <= out <= high:
        raise ControllerError(name + ' is outside the supported numerical range')
    return out


def _array(value, shape, name, bound=1e9):
    def numbers(node):
        if isinstance(node, list):
            return [numbers(item) for item in node]
        return _number(node, -bound, bound, name)
    if not isinstance(value, list):
        raise ControllerError(name + ' must be an array')
    try:
        out = np.asarray(numbers(value), dtype=np.float64)
    except (ValueError, OverflowError, RecursionError) as error:
        raise ControllerError(name + ' has invalid dimensions or numbers') from error
    if out.shape != shape or not np.all(np.isfinite(out)):
        raise ControllerError(name + ' has invalid dimensions or numbers')
    return out


def _spd(value, name):
    scale = max(1.0, float(np.max(np.abs(value))))
    if not np.allclose(value, value.T, rtol=0, atol=1e-10 * scale):
        raise ControllerError(name + ' must be symmetric')
    result = (value + value.T) * 0.5
    try:
        np.linalg.cholesky(result)
    except np.linalg.LinAlgError as error:
        raise ControllerError(name + ' must be positive definite') from error
    return result


def _validate_parameters(config):
    params = config['parameters']
    ranges = {'angle': (-30, 30), 'seconds': (2, 20), 'limit': (.05, 1),
              'p': (0, 3), 'i': (0, 3), 'd': (0, 3), 'arm': (0, 2),
              'qAngle': (1, 200), 'qArm': (.05, 10), 'r': (.1, 20),
              'horizon': (5, 40), 'disturbance': (-.3, .3)}
    _keys(params, list(ranges) + ['method', 'plant', 'antiWindup'], 'parameters')
    for name, bounds in ranges.items():
        _number(params[name], *bounds, 'parameters.' + name)
    if params['method'] != config['method'] or params['plant'] not in ('ideal', 'calibrated'):
        raise ControllerError('Parameter mode does not match controller')
    if type(params['antiWindup']) is not bool or int(params['horizon']) != params['horizon']:
        raise ControllerError('Invalid antiWindup/horizon setting')
    if abs(params['limit'] - config['limit']) > 1e-12:
        raise ControllerError('Parameter limit does not match controller')


class EnergySwing:
    """Experimental energy/inverse-dynamics swing-up, using current rev11 data.

    Adapted structurally from furuta_platform/swingup.py EnergyTeacher. Its
    energy_gain=7000, kick_accel=35 and damping_gain=1.5 are inherited design
    seeds, not a claim of validation for the current 1.2 A hardware path.
    No neural policy or balance law is substituted during the swing phase.
    """
    def __init__(self, config, dt, tau_max, limit):
        _keys(config, ('law', 'energy_gain', 'center_gain', 'damping_gain', 'kick_accel',
                       'speed_target', 'capture_angle', 'capture_pend_rate', 'capture_arm_rate',
                       'release_angle', 'model'), 'swingup')
        if config['law'] != 'energy-inverse-v1':
            raise ControllerError('Unsupported swing-up law')
        self.config = copy.deepcopy(config)
        self.dt, self.tau_max, self.limit = dt, tau_max, limit
        bounds = {'energy_gain': (0, 1e5), 'center_gain': (0, 100), 'damping_gain': (0, 20),
                  'kick_accel': (0, 100), 'speed_target': (.1, 16),
                  'capture_angle': (.001, math.radians(13)), 'capture_pend_rate': (0, .2),
                  'capture_arm_rate': (0, 4), 'release_angle': (.01, math.pi / 3)}
        for key, (low, high) in bounds.items():
            setattr(self, key, _number(config[key], low, high, 'swingup.' + key))
        if self.capture_angle >= self.release_angle:
            raise ControllerError('Swing capture angle must be below the release angle')
        m = config['model']
        _keys(m, ('m00', 'm01', 'm11', 'g', 'Fp', 'Fm', 'b', 'arm_fric_eps',
                  'pend_fl', 'pend_fl_eps', 'pend_damping', 'pend_c2', 'kt'), 'swingup.model')
        self.m00 = _array(m['m00'], (5,), 'swing m00', 10)
        self.m01 = _array(m['m01'], (3,), 'swing m01', 10)
        self.m11 = _number(m['m11'], 1e-8, 1, 'swing m11')
        self.g = _array(m['g'], (3,), 'swing gravity', 100)
        if self.g[2] <= 0 or abs(self.g[0]) + abs(self.g[1]) > 1e-8 * abs(self.g[2]):
            raise ControllerError('Energy law requires downward-zero sine gravity')
        model_bounds = {'Fp': (0, 5), 'Fm': (0, 5), 'b': (0, 5), 'arm_fric_eps': (1e-6, 1),
                        'pend_fl': (0, 1), 'pend_fl_eps': (1e-6, 1), 'pend_damping': (0, 1),
                        'pend_c2': (0, 1), 'kt': (.1, 2)}
        for key, (low, high) in model_bounds.items():
            setattr(self, key, _number(m[key], low, high, 'swing model ' + key))
        # A conservative global bound certifies positive mass matrix for every
        # angle; a finite set of sampled angles would not provide that property.
        minimum_m00 = self.m00[0] - float(np.sum(np.abs(self.m00[1:])))
        maximum_m01 = float(np.sum(np.abs(self.m01)))
        if minimum_m00 * self.m11 - maximum_m01 ** 2 <= 1e-12:
            raise ControllerError('Swing mass matrix is not uniformly positive definite')
        self.reset()

    @staticmethod
    def _state(state):
        try:
            x = np.asarray(state, dtype=np.float64)
        except (ValueError, TypeError, OverflowError) as error:
            raise ControllerError('Invalid swing-up state') from error
        if x.shape != (4,) or not np.all(np.isfinite(x)):
            raise ControllerError('Swing-up state must contain four finite values')
        return [float(v) for v in x]

    def reset(self):
        self.last = {}

    def capture(self, state):
        _, alpha, td, ad = self._state(state)
        error = math.atan2(math.sin(alpha - math.pi), math.cos(alpha - math.pi))
        return abs(error) <= self.capture_angle and abs(ad) <= self.capture_pend_rate and abs(td) <= self.capture_arm_rate

    def step(self, state, budget_s=.01, deadline=None):
        started = time.perf_counter()
        if deadline is None:
            if not math.isfinite(budget_s) or not 0 < budget_s <= self.dt:
                raise ControllerError('Invalid swing-up computation budget')
            deadline = started + budget_s
        elif not math.isfinite(deadline):
            raise ControllerError('Invalid swing-up deadline')
        ClassicalController._deadline(deadline)
        theta, alpha, td, ad = self._state(state)
        ca, sa = math.cos(alpha), math.sin(alpha)
        c2, s2 = math.cos(2 * alpha), math.sin(2 * alpha)
        d, b = self.m00, self.m01
        m00 = float(d[0] + d[1] * ca + d[2] * sa + d[3] * c2 + d[4] * s2)
        m01 = float(b[0] + b[1] * ca + b[2] * sa)
        d00 = float(-d[1] * sa + d[2] * ca - 2 * d[3] * s2 + 2 * d[4] * c2)
        d01 = float(-b[1] * sa + b[2] * ca)
        inertia = m00 - m01 * m01 / self.m11
        if inertia <= 0:
            raise ControllerError('Invalid swing-up effective inertia')
        energy = .5 * self.m11 * ad * ad + float(self.g[2]) * (1 - ca)
        target = float(2 * self.g[2])
        deficit = target - energy
        # E_dot's controlled term is -M01 * alpha_dot * theta_ddot.
        acceleration = -self.energy_gain * deficit * ad * m01 / self.m11
        acceleration -= self.center_gain * theta + self.damping_gain * td
        if abs(ad) < .05 and ca > .95 and energy < .001:
            wrapped = math.atan2(sa, ca)
            away = -(1 if wrapped > 0 else -1 if wrapped < 0 else 0) * (1 if m01 > 0 else -1 if m01 < 0 else 0)
            acceleration += self.kick_accel * (away or 1)
        acceleration = max((-self.speed_target - td) / self.dt,
                           min((self.speed_target - td) / self.dt, acceleration))
        friction0 = (self.Fp if td > 0 else self.Fm) * math.tanh(td / self.arm_fric_eps) + self.b * td
        friction1 = self.pend_damping * ad + self.pend_fl * math.tanh(ad / self.pend_fl_eps) + self.pend_c2 * ad * abs(ad)
        bias0 = d00 * td * ad + d01 * ad * ad + friction0
        bias1 = -.5 * d00 * td * td + float(self.g[0] + self.g[1] * ca + self.g[2] * sa) + friction1
        # Nominal kt converts command torque to estimated physical torque in
        # physics.js. Divide once here; the real torque_path remains unchanged.
        requested = (inertia * acceleration + bias0 - m01 / self.m11 * bias1) / (self.kt * self.tau_max)
        if not all(math.isfinite(v) for v in (requested, energy, target, deficit, acceleration)):
            raise ControllerError('Swing-up command is not finite')
        ClassicalController._deadline(deadline)
        u = max(-self.limit, min(self.limit, requested))
        self.last = {'requested': requested, 'u': u, 'parts': {}, 'integral': 0.0, 'qp': None,
                     'compute_ms': (time.perf_counter() - started) * 1000.0,
                     'energy': energy, 'target': target, 'deficit': deficit,
                     'acceleration': acceleration, 'phase': 'swingup'}
        return u


class ClassicalController:
    """Validate/prepare once at upload; evaluate one local control sample at a time.

    step budget is a software deadline, not a real-time scheduling guarantee.
    A late solve raises before returning an input, including when a NumPy call
    could only be checked after it returned. The caller must handle that error
    by ending control with its existing stop procedure.
    """
    def __init__(self, config, expected_dt=.02, expected_tau=2.52):
        _keys(config, ('schema', 'kind', 'model', 'method', 'dt', 'tau_max',
                       'limit', 'state', 'parameters', 'controller', 'swingup'), 'configuration')
        if type(config['schema']) is not int or config['schema'] != 1 or config['kind'] != 'furuta-classical':
            raise ControllerError('Unsupported controller schema')
        if config['model'] != MODEL or config['state'] != STATE_NAMES:
            raise ControllerError('Unsupported model or state convention')
        if config['method'] not in ('pid', 'lqr', 'lmpc'):
            raise ControllerError('Unsupported classical method')
        self.dt = _number(config['dt'], .001, .1, 'dt')
        tau = _number(config['tau_max'], .001, 100, 'tau_max')
        if abs(self.dt - expected_dt) > 1e-12 or abs(tau - expected_tau) > 1e-12:
            raise ControllerError('Controller sample time or torque scale differs from the receiver')
        self.limit = _number(config['limit'], .05, 1, 'limit')
        _validate_parameters(config)
        self.config = copy.deepcopy(config)
        self.method = config['method']
        control = config['controller']
        if self.method == 'pid':
            _keys(control, ('kp', 'ki', 'kd', 'karm', 'karmRate', 'antiWindup'), 'PID controller')
            self.gains = {key: _number(control[key], -1e4, 1e4, key)
                          for key in ('kp', 'ki', 'kd', 'karm', 'karmRate')}
            if type(control['antiWindup']) is not bool or control['antiWindup'] != config['parameters']['antiWindup']:
                raise ControllerError('Invalid PID antiWindup')
            self.anti_windup = control['antiWindup']
        elif self.method == 'lqr':
            _keys(control, ('K',), 'LQR controller')
            self.K = _array(control['K'], (4,), 'K', 1e4)
        else:
            _keys(control, ('A', 'B', 'Q', 'R', 'P', 'N'), 'LMPC controller')
            self.A = _array(control['A'], (4, 4), 'A', 1e4)
            self.B = _array(control['B'], (4,), 'B', 1e4)
            self.q = _array(control['Q'], (4,), 'Q', 200)
            if not np.all(self.q > 0):
                raise ControllerError('Q diagonal must be positive')
            self.R = _number(control['R'], .1, 20, 'R')
            self.P = _spd(_array(control['P'], (4, 4), 'P'), 'P')
            self.N = int(_number(control['N'], 5, 40, 'N'))
            if self.N != control['N'] or self.N != config['parameters']['horizon']:
                raise ControllerError('Invalid LMPC horizon')
            expected_q = [config['parameters']['qArm'], config['parameters']['qAngle'], .3, 1]
            if not np.allclose(self.q, expected_q, rtol=0, atol=1e-12) or abs(self.R - config['parameters']['r']) > 1e-12:
                raise ControllerError('LMPC cost differs from its parameter snapshot')
            self._prepare_mpc()
        self.swingup = EnergySwing(config['swingup'], self.dt, tau, self.limit)
        self.reset()

    def _prepare_mpc(self):
        # Same condensed cost as mpcSetup: x1..x(N-1) use Q, xN uses P.
        H = np.zeros((self.N, self.N), dtype=np.float64)
        F = np.zeros((self.N, 4), dtype=np.float64)
        S = np.eye(4)
        G = np.zeros((4, self.N), dtype=np.float64)
        with np.errstate(over='raise', invalid='raise'):
            try:
                for k in range(self.N):
                    S = self.A @ S
                    G = self.A @ G
                    G[:, k] += self.B
                    W = self.P if k == self.N - 1 else np.diag(self.q)
                    GtW = G.T @ W
                    H += GtW @ G
                    F += GtW @ S
                H += np.eye(self.N) * self.R
            except FloatingPointError as error:
                raise ControllerError('LMPC prediction matrices overflowed') from error
        if not np.all(np.isfinite(H)) or not np.all(np.isfinite(F)):
            raise ControllerError('LMPC prediction matrices are not finite')
        self.H = _spd(H, 'LMPC Hessian')
        self.F = F
        try:
            condition = float(np.linalg.cond(self.H))
        except np.linalg.LinAlgError as error:
            raise ControllerError('LMPC Hessian conditioning could not be checked') from error
        if not math.isfinite(condition) or condition > 1e12:
            raise ControllerError('LMPC Hessian is too ill-conditioned')

    def reset(self):
        self.integral = 0.0
        self.warm = np.zeros(getattr(self, 'N', 0), dtype=np.float64)
        self.last = {}
        self.swingup.reset()

    @staticmethod
    def _deadline(deadline):
        if time.perf_counter() >= deadline:
            raise ControllerError('Controller calculation exceeded the cycle budget', 'deadline')

    def _qp(self, x, deadline):
        # Feasible active-set method matching control-core.js solveQP. No
        # unconverged iterate is returned for physical execution.
        f = self.F @ x
        u = np.clip(self.warm.copy(), -self.limit, self.limit)
        active = np.where(u <= -self.limit + 1e-10, -1,
                          np.where(u >= self.limit - 1e-10, 1, 0))
        residual = math.inf
        for sweep in range(200):
            self._deadline(deadline)
            grad = self.H @ u + f
            free = np.flatnonzero(active == 0)
            stationary = True
            if free.size:
                stationary = float(np.max(np.abs(grad[free]))) < 1e-7
                if not stationary:
                    try:
                        # H is SPD, hence every principal free-variable block is SPD.
                        chol = np.linalg.cholesky(self.H[np.ix_(free, free)])
                        d = np.linalg.solve(chol.T, np.linalg.solve(chol, -grad[free]))
                    except np.linalg.LinAlgError as error:
                        raise ControllerError('LMPC free-variable solve failed', 'qp') from error
                    self._deadline(deadline)
                    if not np.all(np.isfinite(d)):
                        raise ControllerError('LMPC direction is not finite', 'qp')
                    step, hit, side = 1.0, -1, 0
                    for index, direction in zip(free, d):
                        bound = ((self.limit - u[index]) / direction if direction > 1e-15 else
                                 (-self.limit - u[index]) / direction if direction < -1e-15 else math.inf)
                        if bound < step:
                            step, hit, side = max(0.0, float(bound)), int(index), 1 if direction > 0 else -1
                    u[free] = np.clip(u[free] + step * d, -self.limit, self.limit)
                    if hit >= 0:
                        u[hit], active[hit] = side * self.limit, side
            if stationary:
                release, violation = -1, 1e-7
                for index in np.flatnonzero(active):
                    bad = -grad[index] if active[index] == -1 else grad[index]
                    if bad > violation:
                        release, violation = int(index), float(bad)
                if release >= 0:
                    active[release] = 0
            gradient = self.H @ u + f
            kkt = np.where(u <= -self.limit + 1e-10, np.minimum(gradient, 0),
                           np.where(u >= self.limit - 1e-10, np.maximum(gradient, 0), gradient))
            residual = float(np.max(np.abs(kkt)))
            if not math.isfinite(residual) or not np.all(np.isfinite(u)):
                raise ControllerError('LMPC iterate is not finite', 'qp')
            if residual < 1e-6:
                break
        self._deadline(deadline)
        if residual >= 1e-5:
            raise ControllerError('LMPC did not reach KKT tolerance in 200 iterations', 'qp')
        return u, {'residual': residual, 'iterations': sweep + 1, 'converged': True}

    def step(self, state, budget_s=.01, deadline=None):
        started = time.perf_counter()
        if deadline is None:
            if not math.isfinite(budget_s) or not 0 < budget_s <= self.dt:
                raise ControllerError('Invalid controller computation budget')
            deadline = started + budget_s
        elif not math.isfinite(deadline):
            raise ControllerError('Invalid controller deadline')
        self._deadline(deadline)
        try:
            x = np.asarray(state, dtype=np.float64)
        except (ValueError, TypeError, OverflowError) as error:
            raise ControllerError('Invalid measured state') from error
        if x.shape != (4,) or not np.all(np.isfinite(x)):
            raise ControllerError('Measured state must contain four finite values')
        parts, qp, next_integral, next_warm = {}, None, self.integral, self.warm
        if self.method == 'pid':
            g = self.gains
            candidate = max(-1.0, min(1.0, self.integral + float(x[1]) * self.dt))
            parts = {'P': -g['kp'] * float(x[1]), 'I': -g['ki'] * candidate,
                     'D': -g['kd'] * float(x[3]),
                     'arm': -(g['karm'] * float(x[0]) + g['karmRate'] * float(x[2]))}
            requested = sum(parts.values())
            delta_i = -g['ki'] * (candidate - self.integral)
            if not self.anti_windup or abs(requested) <= self.limit or requested * delta_i < 0:
                next_integral = candidate
            parts['I'] = -g['ki'] * next_integral
            requested = sum(parts.values())
        elif self.method == 'lqr':
            terms = -self.K * x
            parts = {name: float(value) for name, value in zip(('arm', 'angle', 'armRate', 'pendRate'), terms)}
            requested = float(np.sum(terms))
        else:
            sequence, qp = self._qp(x, deadline)
            requested = float(sequence[0])
            next_warm = np.concatenate((sequence[1:], sequence[-1:]))
        if not math.isfinite(requested) or not all(math.isfinite(v) for v in parts.values()):
            raise ControllerError('Controller command is not finite')
        self._deadline(deadline)
        u = max(-self.limit, min(self.limit, requested))
        self.integral, self.warm = next_integral, next_warm
        self.last = {'requested': requested, 'u': u, 'parts': parts, 'integral': self.integral,
                     'qp': qp, 'compute_ms': (time.perf_counter() - started) * 1000.0}
        return u
