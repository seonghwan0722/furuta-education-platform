"""Single RMD commissioning pulse. Run at the rig with power cutoff within reach."""
import argparse
import struct
import time

import can


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pulse', action='store_true',
                        help='Store 100 ms motor watchdog and apply +0.03 A for up to 80 ms')
    args = parser.parse_args()

    with can.Bus(interface='socketcan', channel='can0',
                 can_filters=[{'can_id':0x241,'can_mask':0x7ff,'extended':False}]) as bus:
        def request(opcode, payload=b'\0'*7, timeout=.08):
            bus.send(can.Message(arbitration_id=0x141, is_extended_id=False,
                                 data=bytes([opcode])+payload), timeout=.02)
            deadline = time.monotonic()+timeout
            while (remaining := deadline-time.monotonic()) > 0:
                reply = bus.recv(remaining)
                if reply and not reply.is_error_frame and not reply.is_remote_frame and len(reply.data)==8 and reply.data[0]==opcode:
                    return bytes(reply.data)
            raise TimeoutError(f'No reply to 0x{opcode:02x}')

        def angle():
            return struct.unpack_from('<i', request(0x92), 4)[0]/100

        def status():
            raw = request(0x9a)
            voltage, faults = struct.unpack_from('<HH',raw,4)
            print(f'Voltage {voltage/10:.1f} V, fault flags 0x{faults:04x}',flush=True)
            if faults or not 46 <= voltage/10 <= 50:
                raise RuntimeError('Outside the commissioning voltage window or motor reports a fault')

        status()
        before = angle()
        if args.pulse:
            setting = struct.pack('<I',100)
            if request(0xb3, b'\0'*3+setting)[4:] != setting:
                raise RuntimeError('Motor did not confirm 100 ms watchdog setting')
        try:
            current_units = 3 if args.pulse else 0
            payload = b'\0'*3 + struct.pack('<h',current_units) + b'\0'*2
            deadline = time.monotonic()+.08
            reply = request(0xa1,payload,timeout=.04)
            print('Current command reply:',reply.hex(),flush=True)
            if args.pulse:
                time.sleep(max(0.,deadline-time.monotonic()))
        finally:
            print('Shutdown reply:',request(0x80).hex(),flush=True)
        after = angle()
        status()
        print(f'Angle before {before:+.2f} deg, after {after:+.2f} deg, delta {after-before:+.2f} deg')


if __name__ == '__main__':
    main()
