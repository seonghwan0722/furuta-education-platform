"""RMD CAN-timeout (0xB3) set + cutoff check (2026-11-23). Run at the rig with power cutoff within reach.
Sets the communication-interruption protection time, sends ONE A1 current command, then sends nothing
for --hold seconds. With the watchdog working the motor drops the current after ~timeout and the arm
coasts a few degrees; without it the arm keeps accelerating for the whole hold window."""
import argparse, struct, time
import can

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--timeout-ms', type=int, default=100)
p.add_argument('--amps', type=float, default=0.35)
p.add_argument('--hold', type=float, default=0.5)
p.add_argument('--no-pulse', action='store_true', help='only set and confirm the timeout')
a = p.parse_args()
assert 0 < a.amps <= 0.5 and 0 < a.hold <= 0.6 and 20 <= a.timeout_ms <= 1000
with can.Bus(interface='socketcan', channel='can0',
             can_filters=[{'can_id': 0x241, 'can_mask': 0x7ff, 'extended': False}]) as bus:
    def request(op, payload=b'\0'*7, timeout=.08):
        bus.send(can.Message(arbitration_id=0x141, is_extended_id=False, data=bytes([op])+payload), timeout=.02)
        end = time.monotonic()+timeout
        while (r := end-time.monotonic()) > 0:
            m = bus.recv(r)
            if m and not m.is_error_frame and len(m.data) == 8 and m.data[0] == op:
                return bytes(m.data)
        raise TimeoutError(f'No reply to 0x{op:02x}')
    angle = lambda: struct.unpack_from('<i', request(0x92), 4)[0]/100
    raw = request(0x9a); v, faults = struct.unpack_from('<HH', raw, 4)
    print(f'Voltage {v/10:.1f} V, faults 0x{faults:04x}', flush=True)
    if faults or not 40 <= v/10 <= 52: raise SystemExit('fault or voltage out of range')
    setting = struct.pack('<I', a.timeout_ms)
    echo = request(0xb3, b'\0'*3+setting)
    print('0xB3 reply', echo.hex(), 'confirmed' if echo[4:] == setting else 'NOT CONFIRMED', flush=True)
    if echo[4:] != setting: raise SystemExit('timeout not confirmed')
    if a.no_pulse: raise SystemExit(0)
    a0 = angle()
    try:
        cnt = int(round(a.amps*100))
        bus.send(can.Message(arbitration_id=0x141, is_extended_id=False,
                             data=bytes([0xa1, 0, 0, 0])+struct.pack('<h', cnt)+b'\0\0'), timeout=.02)
        t0 = time.monotonic()
        while time.monotonic()-t0 < a.hold:   # silent window: receive only, send nothing
            bus.recv(0.01)
        a1 = angle()
    finally:
        print('Motor off', request(0x80).hex(), flush=True)
    time.sleep(1.0); a2 = angle()
    print(f'RESULT timeout {a.timeout_ms} ms, {a.amps:.2f} A pulse, travel during {a.hold:.2f} s window {a1-a0:+.1f} deg, total after coast {a2-a0:+.1f} deg', flush=True)
