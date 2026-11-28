"""End-to-end fake TCP receiver check. No CAN or physical I2C is opened.

python kit/test_imu_tcp.py --host-dir <existing pi_host folder>
Use the same Python environment as kit_server (numpy required).
"""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent

# Instrument only the fake hardware constructors, after kit_fake installs them.
# This detects accidental motor/AS5600 access by U even in a hardware-free run.
BOOTSTRAP = r'''
import json, os, sys
sys.path.insert(0, sys.argv.pop(1))
audit = sys.argv.pop(1)
import kit_fake
install = kit_fake.install
def watched_install(rp, session, canguard, *args):
    install(rp, session, canguard, *args)
    counts = {'motor': 0, 'pendulum': 0}
    def tracked(name, constructor):
        def call(*a, **k):
            counts[name] += 1
            with open(audit, 'w') as f: json.dump(counts, f)
            return constructor(*a, **k)
        return call
    rp.Motor = tracked('motor', rp.Motor)
    rp.Pendulum = tracked('pendulum', rp.Pendulum)
kit_fake.install = watched_install
import kit_server
kit_server.main()
'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host-dir', required=True)
    options = parser.parse_args()
    with socket.socket() as reservation:
        reservation.bind(('127.0.0.1', 0))
        port = reservation.getsockname()[1]
    with tempfile.TemporaryDirectory(prefix='pendulum-imu-test-') as directory:
        audit = Path(directory) / 'fake-hardware.json'
        env = dict(os.environ, PYTHONIOENCODING='utf-8')
        process = subprocess.Popen([sys.executable, '-u', '-c', BOOTSTRAP, str(HERE), str(audit),
                                    '--tcp', '127.0.0.1:%d' % port, '--fake',
                                    '--fake-tilt-deg', '0.75', '--fake-tilt-dir', '90',
                                    '--host-dir', options.host_dir, '--log-dir', directory],
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
        connection = None
        try:
            end = time.monotonic() + 8
            while time.monotonic() < end:
                if process.poll() is not None:
                    raise AssertionError(process.stdout.read().decode('utf-8', 'replace'))
                try:
                    connection = socket.create_connection(('127.0.0.1', port), timeout=.2)
                    break
                except OSError:
                    time.sleep(.05)
            assert connection is not None, 'fake server did not start'
            data = b''
            def send(value): connection.sendall((value+'\n').encode())
            def until(prefix, seconds=5):
                nonlocal data
                deadline = time.monotonic() + seconds
                while time.monotonic() < deadline:
                    if b'\n' in data:
                        line, data = data.split(b'\n', 1)
                        line = line.decode('utf-8').strip()
                        if line.startswith(prefix): return line
                        continue
                    connection.settimeout(max(.05, deadline-time.monotonic()))
                    data += connection.recv(65536)
                raise AssertionError('Missing '+prefix)
            send('H')
            assert ' imu1' in until('I ')
            seq = 0
            for number in range(8):
                nonce = 'idle-%d' % number
                send('U '+nonce)
                sample = json.loads(until('U ')[2:])
                assert sample['request_id'] == nonce
                assert sample['seq'] > seq
                assert sample['fake'] is True
                assert abs(sample['tilt_deg']-.75) < .01
                seq = sample['seq']
                time.sleep(.2)
            assert sample['status'] == 'ok', sample
            assert not audit.exists(), 'U opened a motor/AS5600 constructor while idle'
            send('P BEGIN 7 00000000 tanh 0 6,1')
            send('U during-upload')
            paused = json.loads(until('U ')[2:])
            assert paused['status'] == 'paused' and paused['request_id'] == 'during-upload'
            assert 'tilt_deg' not in paused
            assert not audit.exists(), 'U during upload opened fake motor/AS5600'
            send('P END')
            until('E policy ')
            # Real receiver calibration path, using the fake motor and pendulum.
            send('G')
            until('M check')
            send('U during-calibration')
            send('A')
            send('X')
            paused = json.loads(until('U ', 10)[2:])
            assert paused['status'] == 'paused' and paused['request_id'] == 'during-calibration'
            until('G FAIL stop', 10)
            assert audit.exists(), 'calibration did not exercise fake hardware path'
            send('U resumed')
            resumed = json.loads(until('U ')[2:])
            assert resumed['status'] == 'moving', resumed
            assert resumed['seq'] > seq
            # Reconnect starts fresh settling, old connection receives no data.
            connection.close()
            connection = socket.create_connection(('127.0.0.1', port), timeout=2)
            data = b''
            send('H')
            until('I ')
            send('U reconnect')
            reconnected = json.loads(until('U ')[2:])
            assert reconnected['request_id'] == 'reconnect'
            assert reconnected['status'] == 'moving'
            assert reconnected['seq'] > resumed['seq']
            print('PASS: fake TCP handshake, live tilt, idle motor/AS5600 exclusion, upload pause, calibration pause/stop, resume and reconnect')
        finally:
            if connection is not None: connection.close()
            process.terminate()
            try: output = process.communicate(timeout=5)[0]
            except subprocess.TimeoutExpired:
                process.kill()
                output = process.communicate()[0]
            if process.returncode not in (0, 1, -15):
                print(output.decode('utf-8', 'replace')[-1500:])


if __name__ == '__main__': main()
