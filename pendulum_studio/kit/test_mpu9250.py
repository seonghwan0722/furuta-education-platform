"""MPU + passive protocol tests. No CAN, GPIO or I2C hardware is accessed."""
import json
import math
import queue
import struct
import unittest

from mpu9250 import MPU9250, FakeMPU9250, TiltEstimator, axis_map
from kit_server import Server, Stop


class Clock:
    def __init__(self): self.value = 10.0
    def __call__(self): return self.value
    def advance(self, amount=.2): self.value += amount


class Bus:
    def __init__(self, accel=(0, 0, 16384), gyro=(0, 0, 0), identity=0x71):
        self.raw = list(struct.pack('>7h', *accel, 0, *gyro))
        self.identity = identity
        self.writes = []
        self.reads = []
        self.ready = True
        self.closed = False
    def read_byte_data(self, address, register):
        self.reads.append((address, register))
        return self.identity if register == 0x75 else int(self.ready)
    def write_byte_data(self, address, register, value): self.writes.append((address, register, value))
    def read_i2c_block_data(self, address, register, length):
        self.reads.append((address, register, length))
        return self.raw
    def close(self): self.closed = True


class InclinometerTests(unittest.TestCase):
    def make(self, **kwargs):
        self.clock = Clock()
        self.bus = Bus(**kwargs)
        self.opened = []
        def factory(number):
            self.opened.append(number)
            return self.bus
        self.imu = MPU9250(bus_factory=factory, clock=self.clock)
        return self.imu

    def settle(self, reader):
        value = reader.read()
        for _ in range(7):
            self.clock.advance()
            value = reader.read()
        return value

    def test_lazy_open_identity_checked_config_and_units(self):
        imu = self.make(gyro=(131, 0, 0))
        self.assertEqual(self.opened, [])
        value = self.settle(imu)
        self.assertEqual(value['status'], 'ok')
        self.assertEqual(value['tilt_deg'], 0)
        self.assertEqual(value['accel_g'], 1)
        self.assertEqual(value['gyro_dps'], 1)
        self.assertEqual(self.opened, [1])
        self.assertEqual(self.bus.reads[0], (0x68, 0x75))
        self.assertIn((0x68, 0x1C, 0), self.bus.writes)
        self.assertIn((0x68, 0x1B, 0), self.bus.writes)
        self.assertTrue(all(address == 0x68 for address, *rest in self.bus.reads + self.bus.writes))
        self.assertIn((0x68, 0x3B, 14), self.bus.reads)
        imu.close()
        self.assertTrue(self.bus.closed)

    def test_wrong_identity_writes_nothing_and_retries_after_interval(self):
        imu = self.make(identity=0x68)
        result = imu.read()
        self.assertEqual(result['status'], 'unavailable')
        self.assertNotIn('tilt_deg', result)
        self.assertEqual(self.bus.writes, [])
        self.assertTrue(self.bus.closed)
        self.clock.advance(1)
        imu.read()
        self.assertEqual(len(self.opened), 1)
        self.clock.advance(3)
        imu.read()
        self.assertEqual(len(self.opened), 2)

    def test_signed_burst_decoding_and_absolute_tilt(self):
        imu = self.make(accel=(-8192, 0, 14189))
        result = self.settle(imu)
        self.assertAlmostEqual(result['pitch_deg'], 30, delta=.01)
        self.assertAlmostEqual(result['tilt_deg'], 30, delta=.01)
        self.assertAlmostEqual(result['roll_deg'], 0, delta=.01)
        self.bus.raw = list(struct.pack('>7h', 0, 0, -16384, 0, 0, 0, 0))
        self.clock.advance()
        result = imu.read()
        self.assertEqual(result['tilt_deg'], 180)
        self.assertEqual(result['status'], 'moving')

    def test_data_ready_required_no_old_angles_on_missing_data(self):
        imu = self.make()
        result = self.settle(imu)
        seq = result['seq']
        self.bus.ready = False
        self.clock.advance()
        result = imu.read()
        self.assertEqual(result['seq'], seq)
        self.assertEqual(result['status'], 'unavailable')
        self.assertNotIn('roll_deg', result)
        self.bus.ready = True
        self.clock.advance()
        self.assertEqual(imu.read()['status'], 'moving')

    def test_bad_or_zero_acceleration_never_reports_level(self):
        for raw in ([0]*14, [0]*13, [256]*14):
            imu = self.make()
            imu.read()
            self.clock.advance()
            self.bus.raw = raw
            result = imu.read()
            self.assertEqual(result['status'], 'unavailable')
            self.assertNotIn('tilt_deg', result)

    def test_motion_then_rest_and_gap_reset(self):
        self.clock = Clock()
        estimator = TiltEstimator(clock=self.clock)
        for _ in range(5):
            moving = estimator.sample((0, 0, 1), (4, 0, 0))
            self.clock.advance()
        self.assertEqual(moving['status'], 'moving')
        self.assertEqual(moving['tilt_deg'], 0)
        for _ in range(5):
            stable = estimator.sample((0, 0, 1), (0, 0, 0))
            self.clock.advance()
        self.assertEqual(stable['status'], 'ok')
        self.clock.advance(2)
        self.assertEqual(estimator.sample((0, 0, 1), (0, 0, 0))['status'], 'moving')
        self.clock.advance()
        self.assertEqual(estimator.sample((0, 0, 1.15), (0, 0, 0))['status'], 'moving')

    def test_rotated_mount_axis_map(self):
        angle = math.radians(12)
        estimator = TiltEstimator('y,-x,z')
        result = estimator.sample((-math.sin(angle), 0, math.cos(angle)), (0, 0, 0))
        self.assertAlmostEqual(result['roll_deg'], 12, places=3)
        self.assertAlmostEqual(result['tilt_deg'], 12, places=3)
        for invalid in ('x,x,z', 'x,y,-z', 'a,b,c', 'x,y', 'x,y,z,w'):
            with self.assertRaises(ValueError): axis_map(invalid)

    def test_permission_error_has_actionable_message(self):
        def denied(_): raise PermissionError('denied')
        result = MPU9250(bus_factory=denied).read()
        self.assertEqual(result['status'], 'unavailable')
        self.assertIn('i2c 그룹', result['message'])
        self.assertNotIn('tilt_deg', result)

    def test_fake_is_explicit_and_no_hardware_dependency(self):
        self.clock = Clock()
        fake = FakeMPU9250(7, 90, clock=self.clock)
        result = self.settle(fake)
        self.assertTrue(result['fake'])
        self.assertEqual(result['status'], 'ok')
        self.assertAlmostEqual(result['tilt_deg'], 7, places=3)
        seq = result['seq']
        fake.reset()
        self.clock.advance()
        result = fake.read()
        self.assertGreater(result['seq'], seq)
        self.assertEqual(result['status'], 'moving')


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.server = Server.__new__(Server)
        self.server.imu = FakeMPU9250(2)
        self.server.fake = True
        self.server.up = self.server.control_up = None
        self.sent = []
        self.server.send = self.sent.append

    def reply(self): return json.loads(self.sent[-1][2:])

    def test_handshake_capability_and_nonce_roundtrip(self):
        self.server.info()
        self.assertIn(' imu1', self.sent[-1])
        self.server.handle('U abc-123')
        self.assertEqual(self.reply()['request_id'], 'abc-123')
        self.assertTrue(self.reply()['fake'])
        self.assertGreater(self.reply()['tilt_deg'], 1)
        self.server.handle('U')
        self.assertNotIn('request_id', self.reply())

    def test_upload_and_control_poll_pause_without_sensor_access(self):
        def forbidden(): raise AssertionError('IMU read during motor/control operation')
        self.server.imu.read = forbidden
        self.server.up = object()
        self.server.handle('U pending-1')
        self.assertEqual(self.reply()['status'], 'paused')
        self.assertNotIn('tilt_deg', self.reply())
        self.server.up = None
        connection = object()
        class Link: pass
        link = Link()
        link.reply_session = connection
        link.inq = queue.Queue()
        self.server.link = link
        link.inq.put((connection, 'U crossing-2'))
        link.inq.put((connection, 'X'))
        with self.assertRaises(Stop) as caught:
            self.server.poll()
        self.assertEqual(caught.exception.reason, 'stop')
        self.assertEqual(self.reply()['status'], 'paused')
        self.assertEqual(self.reply()['request_id'], 'crossing-2')

    def test_invalid_nonce_is_not_reflected(self):
        for command in ('U bad_nonce', 'U ' + 'a'*64, 'U a b'):
            self.server.handle(command)
            self.assertEqual(self.reply()['status'], 'unavailable')
            self.assertNotIn('request_id', self.reply())


if __name__ == '__main__': unittest.main()
