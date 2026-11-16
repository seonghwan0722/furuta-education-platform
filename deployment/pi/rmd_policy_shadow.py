"""Observe live sensors and print a balance policy prediction without actuation."""
import argparse
import json
import math
from pathlib import Path
import struct
import time

from deployment.pi.encoder import Encoder
from deployment.pi.replay import Guard
from furuta_platform.common import observe
from furuta_platform.policy import Policy


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('profile', type=Path)
    parser.add_argument('policy', type=Path)
    parser.add_argument('--seconds', type=int, choices=range(1, 31), default=10)
    parser.add_argument('--telemetry', action='store_true', help='Print full JSON samples at acquisition rate')
    args = parser.parse_args()

    import can
    from smbus2 import SMBus

    profile = json.loads(args.profile.read_text(encoding='utf-8-sig'))
    motor = profile['can']
    sensor = profile['pendulum_sensor']
    actor = Policy(args.policy)
    arm = Encoder(math.radians(profile['arm_home_deg']), profile['arm_sign'], .03, .10)
    pendulum = Encoder(sensor['upright_count'] * math.tau / 4096, sensor['sign'], .03, .10)
    guard = Guard(actor.meta['config'], .05)
    print('Read-only observation starts in 5 seconds. Move the pendulum gently near upright.', flush=True)
    time.sleep(5)
    with can.Bus(interface='socketcan', channel=motor['interface'], can_filters=[
        {'can_id': motor['angle_reply_id'], 'can_mask': 0x7ff, 'extended': False}
    ]) as bus, SMBus(sensor['i2c_bus']) as i2c:
        deadline = time.monotonic() + args.seconds
        sequence = 0
        next_report = 0.
        while time.monotonic() < deadline:
            start = time.monotonic()
            opcode = motor['output_angle_query']
            bus.send(can.Message(arbitration_id=motor['request_id'], is_extended_id=False,
                                 data=bytes([opcode]) + bytes(7)), timeout=.01)
            while (remaining := start + .03 - time.monotonic()) > 0:
                frame = bus.recv(remaining)
                if (frame is not None and len(frame.data) == 8 and frame.data[0] == opcode
                        and not frame.is_error_frame and not frame.is_remote_frame):
                    break
            else:
                raise TimeoutError('No fresh CAN angle reply')
            arm_time = time.monotonic()
            raw_deg = struct.unpack_from('<i', frame.data, 4)[0] / 100
            arm_raw = math.radians(raw_deg)
            status = i2c.read_byte_data(sensor['i2c_address'], 0x0b)
            if status & 0x38 != 0x20:
                raise RuntimeError('AS5600 magnet status invalid')
            high, low = i2c.read_i2c_block_data(sensor['i2c_address'], 0x0e, 2)
            pend_time = time.monotonic()
            elapsed = pend_time - start
            if elapsed > .05:
                raise TimeoutError('Sensor sample exceeded the shadow freshness budget')
            counts = ((high & 15) << 8) | low
            pend_raw = counts * math.tau / 4096
            theta, arm_speed, arm_valid = arm.update(arm_raw, arm_time)
            alpha, pend_speed, pend_valid = pendulum.update(pend_raw, pend_time)
            alpha = math.atan2(math.sin(alpha), math.cos(alpha))
            if arm_valid and pend_valid:
                state = [theta, alpha, arm_speed, pend_speed]
                inference_start = time.monotonic()
                result = guard.command({'schema':'furuta-io-v1', 'seq':sequence,
                                        'status':'ok', 't_pi_s':start, 'state':state},
                                       time.monotonic(), actor)
                inference_ms = (time.monotonic() - inference_start) * 1000
                if 'fault' in result:
                    raise RuntimeError(result['fault'])
                if args.telemetry:
                    print(json.dumps({
                        't_s': start - (deadline - args.seconds), 'seq': sequence,
                        'arm_deg': math.degrees(theta), 'pendulum_deg': math.degrees(alpha),
                        'arm_rad_s': arm_speed, 'pendulum_rad_s': pend_speed,
                        'observation': observe(*state, actor.meta['config']),
                        'action': result['torque_nm'] / actor.meta['config']['torque_nm'],
                        'requested_nm': result['torque_nm'], 'applied_nm': None,
                        'motor_current_a': None, 'command_sent': False, 'enable': False,
                        'arm_raw_deg': raw_deg, 'pendulum_counts': counts, 'sensor_status': status,
                        'can_ms': (arm_time - start) * 1000, 'sample_ms': elapsed * 1000,
                        'inference_ms': inference_ms,
                        'axis_skew_ms': (pend_time - arm_time) * 1000,
                        'cycle_ms': None if sequence == 1 else (start - previous_start) * 1000,
                        'policy_sha256': actor.meta['sha256'],
                    }, allow_nan=False), flush=True)
                elif start >= next_report:
                    print(json.dumps({'arm_deg':round(math.degrees(theta), 2),
                                      'pendulum_deg':round(math.degrees(alpha), 2),
                                      'simulated_torque_nm':result['torque_nm'],
                                      'enable':False}), flush=True)
                    next_report = start + .25
            previous_start = start
            sequence += 1
            time.sleep(max(0., start + .02 - time.monotonic()))


if __name__ == '__main__':
    main()
