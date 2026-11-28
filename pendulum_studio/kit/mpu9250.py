"""Passive, base-mounted MPU-9250 inclinometer; never imports a motor/CAN driver.

Coordinates after --imu-axes: X forward, Y left, Z up on a level base.
The accelerometer supplies absolute gravity tilt. Gyroscope is a motion gate,
not an integrated attitude estimate. No automatic pose-zero or magnetometer.
Registers: TDK RM-MPU-9250A-00 rev 1.6; sensitivities: PS-MPU-9250A-01.
"""
import math
import time


def axis_map(value):
    """A proper signed permutation from sensor axes to base axes."""
    names = str(value).lower().split(",")
    if len(names) != 3 or any(n not in ("x", "y", "z", "-x", "-y", "-z") for n in names):
        raise ValueError("imu axes must be three signed axes, e.g. x,y,z or y,-x,z")
    indices = ["xyz".index(n[-1]) for n in names]
    signs = [-1 if n.startswith("-") else 1 for n in names]
    inversions = sum(indices[i] > indices[j] for i in range(3) for j in range(i + 1, 3))
    if len(set(indices)) != 3 or (-1) ** inversions * math.prod(signs) != 1:
        raise ValueError("imu axes must describe a right-handed rotation without repeated axes")
    return tuple(zip(indices, signs))


def gravity_angles(accel):
    x, y, z = accel
    return (math.degrees(math.atan2(y, z)),
            math.degrees(math.atan2(-x, math.hypot(y, z))),
            math.degrees(math.atan2(math.hypot(x, y), z)))


def smbus_factory(number):
    try:
        from smbus2 import SMBus
    except ImportError:
        try:
            from smbus import SMBus
        except ImportError as error:
            raise RuntimeError("smbus2 또는 python3-smbus를 Pi 서비스 Python에 설치해 주세요") from error
    return SMBus(number)


class TiltEstimator:
    def __init__(self, axes="x,y,z", clock=time.monotonic):
        self.axes = axis_map(axes)
        self.clock = clock
        self.seq = 0
        self.reset()

    def reset(self):
        self.filtered = None
        self.previous = None
        self.previous_time = None
        self.still_since = None
        self.still_count = 0

    def sample(self, accel, gyro, fake=False):
        now = self.clock()
        a = tuple(accel[i] * sign for i, sign in self.axes)
        g = tuple(gyro[i] * sign for i, sign in self.axes)
        if not all(math.isfinite(v) for v in a + g):
            raise ValueError("IMU가 유효하지 않은 값을 보냈습니다")
        magnitude, spin = math.sqrt(sum(v*v for v in a)), math.sqrt(sum(v*v for v in g))
        if magnitude < 0.1 or magnitude > 1.9:
            self.reset()
            raise ValueError("가속도 범위를 확인해 주세요. 센서 데이터가 유효하지 않습니다")
        gap = self.previous_time is None or now - self.previous_time > 0.75
        change = 0 if self.previous is None else math.sqrt(sum((v-p)**2 for v, p in zip(a, self.previous)))
        stationary = abs(magnitude - 1.0) <= 0.08 and spin <= 3.0 and change <= 0.035
        if gap or not stationary:
            self.still_since = None
            self.still_count = 0
            self.filtered = None
        if stationary:
            if self.still_since is None:
                self.still_since = now
            self.still_count += 1
        settled = stationary and self.still_count >= 4 and now - self.still_since >= 0.6
        # Moving samples remain visible without feeding dynamic acceleration into
        # the low-pass estimate. Reinitialize after motion, gaps and reconnects.
        if stationary:
            if self.filtered is None:
                self.filtered = a
            else:
                dt = max(0, now - self.previous_time)
                weight = 1.0 - math.exp(-dt / 0.2)
                self.filtered = tuple(p + weight*(v-p) for v, p in zip(a, self.filtered))
            angles = gravity_angles(self.filtered)
        else:
            angles = gravity_angles(a)
        self.previous, self.previous_time = a, now
        self.seq += 1
        return dict(status="ok" if settled else "moving", roll_deg=round(angles[0], 3),
                    pitch_deg=round(angles[1], 3), tilt_deg=round(angles[2], 3),
                    accel_g=round(magnitude, 4), gyro_dps=round(spin, 3), seq=self.seq,
                    fake=fake, message="받침 기울기 측정 중" if settled else "받침을 조정한 뒤 잠시 멈춰 주세요")


class MPU9250:
    def __init__(self, bus=1, address=0x68, axes="x,y,z", bus_factory=smbus_factory,
                 clock=time.monotonic, retry_seconds=3.0):
        if not isinstance(bus, int) or isinstance(bus, bool) or bus < 0:
            raise ValueError("imu bus must be a non-negative bus number")
        if address not in (0x68, 0x69):
            raise ValueError("imu address must be 0x68 or 0x69")
        self.bus_number, self.address = bus, address
        self.factory, self.clock = bus_factory, clock
        self.retry_seconds = retry_seconds
        self.estimator = TiltEstimator(axes, clock)
        self.bus = None
        self.ready_at = 0
        self.retry_at = 0
        self.error = "IMU 연결을 확인하는 중입니다"

    def reset(self):
        self.estimator.reset()

    def close(self):
        if self.bus is not None:
            try:
                self.bus.close()
            except OSError:
                pass
        self.bus = None
        self.estimator.reset()

    def _open(self):
        self.bus = self.factory(self.bus_number)
        identity = self.bus.read_byte_data(self.address, 0x75)
        if identity != 0x71:
            raise ValueError("WHO_AM_I=0x%02X: MPU-9250(0x71)이 아닙니다. 주소와 센서 종류를 확인해 주세요" % identity)
        # Only the explicitly selected, identity-checked IMU is configured.
        for register, value in ((0x6B, 0x01), (0x6C, 0x00), (0x1A, 0x04),
                                (0x19, 0x09), (0x1B, 0x00), (0x1C, 0x00), (0x1D, 0x04), (0x38, 0x01)):
            self.bus.write_byte_data(self.address, register, value)
        self.ready_at = self.clock() + 0.1

    def _unavailable(self, message):
        return dict(status="unavailable", seq=self.estimator.seq, fake=False, message=message)

    def read(self):
        now = self.clock()
        if self.bus is None and now < self.retry_at:
            return self._unavailable(self.error)
        try:
            if self.bus is None:
                self._open()
            if now < self.ready_at:
                return self._unavailable("IMU가 준비 중입니다. 잠시 기다려 주세요")
            # DATA_RDY must be new since the previous read; no reuse of stale data.
            if not self.bus.read_byte_data(self.address, 0x3A) & 0x01:
                self.estimator.reset()
                return self._unavailable("새 IMU 측정값이 없습니다. 배선과 센서를 확인해 주세요")
            raw = self.bus.read_i2c_block_data(self.address, 0x3B, 14)
            if len(raw) != 14 or any(not isinstance(v, int) or v < 0 or v > 255 for v in raw):
                raise ValueError("IMU 데이터 길이/바이트 오류")
            values = []
            for i in range(0, 14, 2):
                value = (raw[i] << 8) | raw[i+1]
                values.append(value - 65536 if value >= 32768 else value)
            return self.estimator.sample(tuple(v / 16384.0 for v in values[:3]),
                                         tuple(v / 131.0 for v in values[4:]))
        except (OSError, RuntimeError, ValueError) as error:
            if isinstance(error, PermissionError):
                self.error = "/dev/i2c-%d 접근 권한이 없습니다. Pi 서비스 계정의 i2c 그룹을 확인해 주세요" % self.bus_number
            else:
                self.error = "IMU 읽기 실패 (버스 %d, 주소 0x%02X): %s" % (self.bus_number, self.address, error)
            self.close()
            self.retry_at = self.clock() + self.retry_seconds
            return self._unavailable(self.error[:220])


class FakeMPU9250:
    """Deterministic, stationary virtual base. Never opens hardware."""
    def __init__(self, tilt_deg=0.0, direction_deg=0.0, clock=time.monotonic):
        if not all(math.isfinite(v) for v in (tilt_deg, direction_deg)) or not -180 <= tilt_deg <= 180:
            raise ValueError("fake IMU tilt must be finite and within -180..180 degrees")
        tilt, direction = math.radians(tilt_deg), math.radians(direction_deg)
        self.accel = (math.sin(tilt)*math.cos(direction), math.sin(tilt)*math.sin(direction), math.cos(tilt))
        self.estimator = TiltEstimator(clock=clock)

    def read(self):
        return self.estimator.sample(self.accel, (0, 0, 0), fake=True)

    def reset(self):
        self.estimator.reset()

    def close(self):
        self.reset()
