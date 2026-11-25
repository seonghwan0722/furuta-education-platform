"""실험 1: 진자 자유진동 (팔은 0x78 브레이크로 고정, 토크 명령 없음).

  python exp1_free_swing.py [--wait 90] [--record 15]

1. 세션 시작 점검 -> 0x78 브레이크 잠금, 0x9A 로 잠김(00) 확인
2. 진자가 영점에서 15° 넘게 들릴 때까지 최대 --wait 초 대기 (AS5600 ~1 kHz 폴링)
3. 그때부터 --record 초 동안 AS5600 RAW 를 기록 (목표 500 Hz 이상)
4. 기록 앞뒤로 0x92 를 읽어 팔이 움직이지 않았는지 확인
기록: logs/exp1_free_swing_YYYYmmdd_HHMMSS.csv (t[s], raw, alpha[rad], alpha_sign=+1, 영점 2027)
"""
import os
import sys
import csv
import math
import time
import argparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import canguard  # noqa: E402
import session  # noqa: E402

ZERO = session.ZERO_RAW
ALPHA_SIGN = +1
TRIGGER_DEG = 15.0


def alpha(raw):
    a = ALPHA_SIGN * (raw - ZERO) * 2 * math.pi / 4096
    return (a + math.pi) % (2 * math.pi) - math.pi


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wait", type=float, default=90.0)
    ap.add_argument("--record", type=float, default=15.0)
    a = ap.parse_args()
    from smbus2 import SMBus
    bus, i2c = session.open_bus(), SMBus(1)

    def rd():
        hi, lo = i2c.read_i2c_block_data(0x36, 0x0C, 2)
        return ((hi & 0x0F) << 8) | lo

    path = session.log_path("exp1_free_swing")
    rows = []
    try:
        pf = session.preflight(bus, i2c, "exp1_free_swing")
        if pf.get("brake") != 0:             # 이미 잠겨 있으면 명령을 보내지 않음
            r = session._xfer(bus, 0x78)
            print("0x78 응답:", r.hex(" ") if r else None)
            time.sleep(0.05)
            d = session._xfer(bus, 0x9A)
            if d is None or d[3] != 0:
                raise RuntimeError(f"브레이크 잠김 확인 실패: {d.hex(' ') if d else None}")
        a92_0 = session.read_a92(bus)
        print(f"브레이크 잠김 확인, 0x92 {a92_0:.2f}°. 진자를 옆으로 들었다 놓으세요 "
              f"(최대 {a.wait:.0f} s 대기)", flush=True)

        t0 = time.time()
        while True:
            r = rd()
            if abs(math.degrees(alpha(r))) > TRIGGER_DEG:
                break
            if time.time() - t0 > a.wait:
                raise RuntimeError("대기 시간 안에 진자가 15° 넘게 들리지 않음")
            time.sleep(0.001)
        print("감지, 기록 시작", flush=True)
        ts = time.perf_counter()
        while (now := time.perf_counter() - ts) < a.record:
            rows.append((now, rd()))
        a92_1 = session.read_a92(bus)
        dt = [rows[i + 1][0] - rows[i][0] for i in range(len(rows) - 1)]
        print(f"기록 {len(rows)}점, 평균 {len(rows) / a.record:.0f} Hz, 최대 간격 {max(dt) * 1000:.1f} ms")
        print(f"0x92 전후: {a92_0:.2f}° -> {a92_1:.2f}° (차이 {a92_1 - a92_0:+.2f}°, 팔 고정 확인)")
        al = [alpha(r) for _, r in rows]
        print(f"α 범위 {math.degrees(min(al)):+.1f}° ~ {math.degrees(max(al)):+.1f}°, "
              f"마지막 1 s 평균 RAW {sum(r for t, r in rows if t > a.record - 1) / max(1, sum(1 for t, _ in rows if t > a.record - 1)):.1f}")
    except (session.PreflightError, canguard.CanGuardError, RuntimeError) as e:
        print("중단:", e)
    finally:
        try:
            session.record_end_angle(bus)
        except Exception:
            pass
        bus.shutdown()
        i2c.close()
        if rows:
            with open(path, "w", newline="") as fh:
                w = csv.writer(fh)
                w.writerow(["t", "raw", "alpha"])
                for t, r in rows:
                    w.writerow([f"{t:.5f}", r, f"{alpha(r):.5f}"])
            print("기록:", path)


if __name__ == "__main__":
    main()
