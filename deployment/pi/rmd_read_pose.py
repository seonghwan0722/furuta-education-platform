"""Read a stationary Furuta pose. Only sends the RMD output-angle query."""
import json
import statistics
import struct
import time

import can
from smbus2 import SMBus


def sample_pose():
    arm_angles = []
    pendulum_counts = []
    with can.Bus(interface='socketcan', channel='can0', can_filters=[
        {'can_id': 0x241, 'can_mask': 0x7ff, 'extended': False}
    ]) as bus, SMBus(1) as sensor:
        for _ in range(12):
            bus.send(can.Message(arbitration_id=0x141, is_extended_id=False,
                                 data=b'\x92' + b'\0' * 7), timeout=.02)
            deadline = time.monotonic() + .06
            while (remaining := deadline - time.monotonic()) > 0:
                message = bus.recv(remaining)
                if (message is not None and not message.is_error_frame
                        and not message.is_remote_frame and len(message.data) == 8
                        and message.data[0] == 0x92):
                    arm_angles.append(struct.unpack_from('<i', message.data, 4)[0] / 100)
                    status = sensor.read_byte_data(0x36, 0x0b)
                    if status & 0x38 != 0x20:
                        raise RuntimeError(f'AS5600 magnet status invalid: {status:#04x}')
                    high, low = sensor.read_i2c_block_data(0x36, 0x0e, 2)
                    pendulum_counts.append(((high & 15) << 8) | low)
                    break
            time.sleep(.01)
    if len(arm_angles) < 8:
        raise RuntimeError(f'Only {len(arm_angles)} valid CAN angle samples')
    reference = pendulum_counts[0]
    unwrapped = [reference + ((value - reference + 2048) % 4096 - 2048)
                 for value in pendulum_counts]
    return {
        'samples': len(arm_angles),
        'arm_deg_median': statistics.median(arm_angles),
        'arm_span_deg': max(arm_angles) - min(arm_angles),
        'pendulum_count_median': statistics.median(unwrapped) % 4096,
        'pendulum_span_counts': max(unwrapped) - min(unwrapped),
    }


if __name__ == '__main__':
    print(json.dumps(sample_pose()))
