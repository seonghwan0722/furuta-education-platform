"""Log RMD current and output angle during a single commissioning pulse."""
import argparse
import json
import signal
import struct
import time


PULSE_SECONDS = 0.08
SAMPLE_SECONDS = 0.01


def capture(request, pulse_counts, rows):
    started = time.monotonic()

    def record(phase, kind, **values):
        rows.append({
            't_ms': round((time.monotonic() - started) * 1000, 3),
            'phase': phase, 'kind': kind, **values,
        })

    def status(phase):
        response = request(0x9A)
        voltage, flags = struct.unpack_from('<HH', response, 4)
        record(phase, 'status', voltage_v=voltage / 10, fault_flags=flags)
        if flags or not 46 <= voltage / 10 <= 50:
            raise RuntimeError('RMD fault or voltage outside the existing test window')

    def feedback(phase, target, deadline=None, reply=None):
        data = request(0x9C, deadline=deadline) if reply is None else reply
        current, speed = struct.unpack_from('<hh', data, 2)
        record(phase, 'current', target_a=target, reported_a=current / 100,
               speed_deg_s=speed, frame=data.hex())
        raw = request(0x92, deadline=deadline)
        angle = struct.unpack_from('<i', raw, 4)[0] / 100
        record(phase, 'angle', angle_deg=angle, frame=raw.hex())
        return angle, current, speed

    status('before')
    baseline = []
    for _ in range(10):
        baseline.append(feedback('before', None))
        time.sleep(SAMPLE_SECONDS)
    if not pulse_counts:
        return
    angles = [row[0] for row in baseline]
    last_angle = angles[-1]
    if max(angles) - min(angles) > 0.1 or any(i or speed for _, i, speed in baseline):
        raise RuntimeError('Baseline is not stationary with zero reported current')

    target = pulse_counts / 100
    payload = struct.pack('<3xh2x', pulse_counts)
    deadline = time.monotonic() + PULSE_SECONDS
    try:
        record('pulse', 'command', target_a=target)
        reply = request(0xA1, payload, deadline)
        while deadline - time.monotonic() >= SAMPLE_SECONDS:
            angle, _, _ = feedback('pulse', target, deadline, reply)
            if abs(angle - last_angle) >= 1:
                raise RuntimeError('Output shaft reached the 1 degree test limit')
            reply = None
            time.sleep(min(SAMPLE_SECONDS, max(0., deadline - time.monotonic())))
    finally:
        # Send shutdown before printing or doing any further measurements.
        record('stop', 'shutdown_requested')
        reply = request(0x80)
        record('stop', 'shutdown_ack', frame=reply.hex())

    for _ in range(15):
        feedback('after', None)
        time.sleep(SAMPLE_SECONDS)
    status('after')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pulse-counts', type=int, choices=(-3, 3),
                        help='Send a single ±0.03 A pulse. Omit for sensor reads only.')
    args = parser.parse_args()
    import can

    def interrupted(signum, _frame):
        raise KeyboardInterrupt(f'interrupted by signal {signum}')

    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGHUP, interrupted)
    rows = []
    try:
        with can.Bus(interface='socketcan', channel='can0', can_filters=[
            {'can_id': 0x241, 'can_mask': 0x7ff, 'extended': False}
        ]) as bus:
            def request(opcode, payload=bytes(7), deadline=None):
                now = time.monotonic()
                end = now + .04 if deadline is None else min(now + .008, deadline)
                if now >= end:
                    raise TimeoutError(f'Missed deadline before 0x{opcode:02x}')
                bus.send(can.Message(arbitration_id=0x141, is_extended_id=False,
                                     data=bytes([opcode]) + payload), timeout=min(.005, end - now))
                while (remaining := end - time.monotonic()) > 0:
                    reply = bus.recv(remaining)
                    if (reply is not None and not reply.is_error_frame and not reply.is_remote_frame
                            and len(reply.data) == 8 and reply.data[0] == opcode):
                        return bytes(reply.data)
                raise TimeoutError(f'No RMD reply to 0x{opcode:02x}')

            capture(request, args.pulse_counts, rows)
    except (KeyboardInterrupt, OSError, RuntimeError, can.CanError) as exc:
        rows.append({'kind': 'error', 'message': str(exc)})
        return 1
    finally:
        for row in rows:
            print(json.dumps(row), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
