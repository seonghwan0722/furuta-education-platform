"""Evaluate the saved simulation LQR against timestamped sensor logs, with motor output disabled."""
import argparse
import json
import math
from pathlib import Path

from .replay import Guard


class BalanceShadow:
    def __init__(self, config, timeout):
        residual = config['residual']
        self.gain, = residual['balance_gain']
        self.capture = residual['capture_abs']
        if len(self.gain) != 4 or not all(math.isfinite(x) for x in self.gain):
            raise ValueError('Expected four finite balance gains')
        if len(self.capture) != 4 or not all(math.isfinite(x) and x > 0 for x in self.capture):
            raise ValueError('Expected four positive simulation capture limits')
        if not math.isfinite(config['torque_nm']) or config['torque_nm'] <= 0:
            raise ValueError('Invalid simulation torque scale')
        if not math.isfinite(timeout):
            raise ValueError('Expected a finite freshness budget')
        self.guard = Guard(config, timeout)

    def command(self, row):
        eligible = False
        try:
            packet = row['packet']

            class Actor:
                def predict(actor, obs):
                    nonlocal eligible
                    theta, alpha, arm_speed, pend_speed = packet['state']
                    state = theta, math.atan2(math.sin(alpha), math.cos(alpha)), arm_speed, pend_speed
                    eligible = all(abs(x) <= bound for x, bound in zip(state, self.capture))
                    action = -sum(gain * value for gain, value in zip(self.gain, state))
                    return [max(-1., min(1., action)) if eligible else 0.]

            result = self.guard.command(packet, row['receive_t_pi_s'], Actor())
        except (KeyError, TypeError) as exc:
            self.guard.latched = True
            result = {'fault': str(exc), 'torque_nm': 0.}
        return {
            **result,
            'simulated_torque_nm': result['torque_nm'],
            'torque_nm': 0.,
            'enable': False,
            'inside_simulation_capture': eligible and 'fault' not in result,
            'mode': 'balance_shadow',
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config', type=Path, help='Saved residual swing-up config.json')
    parser.add_argument('records', type=Path, help='Sensor JSONL in the replay format')
    parser.add_argument('--timeout', required=True, type=float, help='Measured sample freshness budget in seconds')
    args = parser.parse_args()
    shadow = BalanceShadow(json.loads(args.config.read_text(encoding='utf-8-sig')), args.timeout)
    with args.records.open(encoding='utf-8-sig') as records:
        for line in records:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                row = {}
            print(json.dumps(shadow.command(row), allow_nan=False))


if __name__ == '__main__':
    main()
