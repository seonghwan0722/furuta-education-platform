"""하드웨어 확인 (토크 명령 없음).

  python check_hw.py status          # 0x78 브레이크 잠금 후 0x9A 상태, 0x92 다회전 각도
  python check_hw.py alpha [-s 5]    # AS5600 RAW 와 α(alpha_sign=+1, offset 2027) 를 s 초 동안 기록
  python check_hw.py angle92 [-s 5]  # 0x92 다회전 각도를 s 초 동안 20 Hz 로 읽기
  python check_hw.py turn92 -s 20    # 0x77 해제(토크 없음) -> 손으로 팔 회전 중 0x92 기록 -> 0x78 잠금
"""
import sys
import math
import time
import argparse

REQ, RSP = 0x141, 0x241
OFFSET_RAW = 2027


def can_bus():
    import can
    import session
    bus = can.interface.Bus(channel="can0", interface="socketcan")
    try:
        session.preflight(bus, None, "check_hw")
    except Exception:
        bus.shutdown()
        raise
    return bus


def xfer(bus, cmd, payload=b"", timeout=0.05):
    import can
    data = bytearray(8)
    data[0] = cmd
    data[1:1 + len(payload)] = payload
    bus.send(can.Message(arbitration_id=REQ, data=bytes(data), is_extended_id=False))
    deadline = time.time() + timeout
    while time.time() < deadline:
        m = bus.recv(timeout=max(0.0, deadline - time.time()))
        if m is None:
            break
        if m.arbitration_id == RSP and m.data[0] == cmd:
            return bytes(m.data)
    return None


def read_92(bus):
    d = xfer(bus, 0x92)
    if d is None:
        return None, None
    return int.from_bytes(d[4:8], "little", signed=True) * 0.01, d


def cmd_status(_):
    bus = can_bus()
    try:
        r78 = xfer(bus, 0x78)
        print("0x78 응답:", r78.hex(" ") if r78 else None)
        d = xfer(bus, 0x9A)
        if d:
            print(f"0x9A: {d.hex(' ')} | 온도 {d[1]}°C, MOS {d[2]}°C, 브레이크 {d[3]}, "
                  f"전압 {int.from_bytes(d[4:6], 'little') * 0.1:.1f} V, 에러 0x{int.from_bytes(d[6:8], 'little'):04x}")
        else:
            print("0x9A 응답 없음")
        deg, raw = read_92(bus)
        print("0x92:", raw.hex(" ") if raw else None, f"-> {deg:.2f}°" if deg is not None else "")
    finally:
        bus.shutdown()


def cmd_angle92(a):
    bus = can_bus()
    try:
        t0 = time.time()
        vals = []
        while time.time() - t0 < a.seconds:
            deg, _ = read_92(bus)
            vals.append(deg)
            print(f"{time.time() - t0:5.2f}s  {deg}")
            time.sleep(0.05)
        v = [x for x in vals if x is not None]
        if v:
            print(f"min {min(v):.2f}  max {max(v):.2f}  변화 {max(v) - min(v):.2f}°")
    finally:
        bus.shutdown()


def cmd_turn92(a):
    """0x77 브레이크 해제(토크 없음) -> 손으로 팔 돌리는 동안 0x92 기록 -> 무조건 0x78 잠금."""
    bus = can_bus()
    try:
        print("0x77:", xfer(bus, 0x77))
        time.sleep(0.05)
        d = xfer(bus, 0x9A)
        print("해제 후 0x9A 브레이크 바이트(1=해제):", d[3] if d else None, flush=True)
        cmd_angle92_bus(bus, a.seconds)
    finally:
        for _ in range(2):
            xfer(bus, 0x78)
        d = xfer(bus, 0x9A)
        print("0x78 잠금 전송. 0x9A 브레이크 바이트:", d[3] if d else None)
        bus.shutdown()


def cmd_angle92_bus(bus, seconds):
    t0 = time.time()
    v = []
    still_since = None
    while time.time() - t0 < seconds:
        deg, _ = read_92(bus)
        if deg is not None:
            if v and abs(deg - v[-1]) < 0.2:
                still_since = still_since or time.time()
            else:
                still_since = None
            v.append(deg)
        print(f"{time.time() - t0:5.2f}s  {deg}", flush=True)
        if v and abs(v[-1] - v[0]) > 30 and still_since and time.time() - still_since > 2.0:
            print("큰 이동 후 2초 정지 -> 종료")
            break
        time.sleep(0.05)
    if v:
        print(f"시작 {v[0]:.2f}  끝 {v[-1]:.2f}  끝-시작 {v[-1] - v[0]:+.2f}°  min {min(v):.2f}  max {max(v):.2f}")


def cmd_alpha(a):
    from smbus2 import SMBus
    bus = SMBus(1)
    t0 = time.time()
    al = []
    first = None
    while time.time() - t0 < a.seconds:
        hi, lo = bus.read_i2c_block_data(0x36, 0x0C, 2)
        raw = ((hi & 0x0F) << 8) | lo
        alpha = (raw - OFFSET_RAW) * 2 * math.pi / 4096
        alpha = (alpha + math.pi) % (2 * math.pi) - math.pi
        al.append(alpha)
        if abs(alpha - al[0]) > math.radians(10) and first is None:
            first = (time.time() - t0, alpha)
            print(f"*** 첫 큰 변위: {math.degrees(alpha - al[0]):+.1f}° (α {alpha:+.3f} rad)")
        if first and time.time() - t0 - first[0] > 8:
            break
        print(f"{time.time() - t0:5.2f}s  raw {raw:4d}  α(+1) {alpha:+.3f} rad ({math.degrees(alpha):+6.1f}°)")
        time.sleep(0.05)
    print(f"α min {min(al):+.3f}  max {max(al):+.3f}  마지막 {al[-1]:+.3f} rad")
    print("첫 큰 변위:", None if first is None else f"t={first[0]:.2f}s α={first[1]:+.3f} rad")
    bus.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["status", "alpha", "angle92", "turn92"])
    ap.add_argument("-s", "--seconds", type=float, default=3.0)
    a = ap.parse_args()
    {"status": cmd_status, "alpha": cmd_alpha, "angle92": cmd_angle92, "turn92": cmd_turn92}[a.mode](a)
