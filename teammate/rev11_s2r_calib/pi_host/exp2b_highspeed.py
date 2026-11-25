"""실험 2b: 고속 마찰 확인 (진자 단 상태) — 모터 사용. 실행 전 사용자 확인 필수, 사용자는 PSU 스위치 옆.

  python exp2b_highspeed.py            # 점검만 (세션 시작 점검, 모터 명령 없음)
  python exp2b_highspeed.py --go       # 실행

목적: 브리지 보상 (c) 시뮬에서 나온 팔 속도(최대 831 dps)까지 실험 2 마찰 모델(방향별 쿨롱 + 점성)이 맞는지 확인.
펄스: |iq| = 80, 120, 160, 200 (0.8~2.0 A), 각 +, − 한 번씩, 0.45 s (시정수 J/b ≈ 0.1 s 의 4.5 배 -> 일정 속도 도달).
펄스 뒤 iq 0 으로 팔이 멈추고 진자가 어느 정도 가라앉을 때까지 대기(최소 1 s, 최대 8 s).
이 스크립트에서만 한계를 올림: iq 상한 200(2.0 A), 팔 속도 1100 dps, 시작 대비 팔 각도 ±500°. 다른 스크립트는 그대로.
나머지는 실험 2 와 같음: 10 ms 주기 0xA1 -> 0x92 -> AS5600, 원시 CAN 전부 기록, 세션 시작 점검,
종료(정상·예외·Ctrl+C)는 항상 iq 0 -> 0x81 -> 0x78. 0xB3 은 쓰지 않는다.
기록: logs/exp2b_highspeed_<stamp>.csv, _can.csv, _zero.csv
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

REQ, RSP = 0x141, 0x241
IQ_HARD_MAX = 200                # 2.0 A, 이 스크립트에서만
DT = 0.010
ID_LEVELS = [80, 120, 160, 200]
ID_PULSE_S = 0.45
SWEEP_IQ = 60
SWEEP_PULSE_S = 0.25
SWEEP_TARGET_DEG = 360.0
SWEEP_MAX_STEPS = 16
SETTLE_MIN_S, SETTLE_MAX_S = 1.0, 8.0
STILL_RAW = 3                    # 0.5 s 동안 진자 RAW 변동 이하
LIM_DPS, LIM_DEG, LIM_PEND = 1100, 500.0, 25.0


class Abort(RuntimeError):
    pass


class Rig:
    def __init__(self, can_log_path):
        import can
        from smbus2 import SMBus
        self.can = can
        self.bus = session.open_bus()
        self.i2c = SMBus(1)
        self.t0 = time.perf_counter()
        self.canlog = open(can_log_path, "w", newline="")
        self.cw = csv.writer(self.canlog)
        self.cw.writerow(["t", "dir", "id", "data"])
        self.miss = 0

    def now(self):
        return time.perf_counter() - self.t0

    def close(self):
        try:
            self.bus.shutdown()
        finally:
            self.i2c.close()
            self.canlog.close()

    def raw(self):
        hi, lo = self.i2c.read_i2c_block_data(0x36, 0x0C, 2)
        return ((hi & 0x0F) << 8) | lo

    def _rx(self, timeout):
        m = self.bus.recv(timeout=timeout)
        if m is not None:
            self.cw.writerow([f"{self.now():.5f}", "rx", f"{m.arbitration_id:03X}", bytes(m.data).hex(" ")])
            canguard.foreign_frame(m)
        return m

    def xfer(self, data8, timeout=0.004):
        canguard.fast_check()
        while self._rx(0.0) is not None:          # 늦게 온 응답 비우기(기록은 남김)
            pass
        self.cw.writerow([f"{self.now():.5f}", "tx", f"{REQ:03X}", bytes(data8).hex(" ")])
        self.bus.send(self.can.Message(arbitration_id=REQ, data=bytes(data8), is_extended_id=False))
        end = time.perf_counter() + timeout
        wrong = None
        while time.perf_counter() < end:
            m = self._rx(max(0.0, end - time.perf_counter()))
            if m is None:
                break
            if m.arbitration_id == RSP:
                if m.data[0] == data8[0]:
                    self.miss = 0
                    return bytes(m.data)
                wrong = bytes(m.data)
        if wrong is not None:
            raise Abort(f"0x{data8[0]:02X} 에 다른 명령의 응답 {wrong.hex(' ')} (응답 반복 상태) -> 중단")
        self.miss += 1
        if self.miss >= 3:
            raise Abort(f"모터 응답 3회 연속 없음 (마지막 명령 0x{data8[0]:02X})")
        return None

    def cmd(self, c):
        return self.xfer(bytes([c, 0, 0, 0, 0, 0, 0, 0]))

    def torque(self, iq):
        iq = max(-IQ_HARD_MAX, min(IQ_HARD_MAX, int(iq)))
        v = iq & 0xFFFF
        d = self.xfer(bytes([0xA1, 0, 0, 0, v & 0xFF, v >> 8, 0, 0]))
        if d is None:
            return None
        return (int.from_bytes(d[2:4], "little", signed=True), int.from_bytes(d[4:6], "little", signed=True),
                int.from_bytes(d[6:8], "little", signed=True))

    def a92(self):
        d = self.cmd(0x92)
        return None if d is None else int.from_bytes(d[4:8], "little", signed=True) * 0.01


def alpha_deg(raw):
    a = (raw - session.ZERO_RAW) * 360.0 / 4096
    return (a + 180.0) % 360.0 - 180.0


class Runner:
    def __init__(self, rig, w):
        self.rig, self.w = rig, w
        self.a_start = None
        self.last = dict(a92=None, raw=None)
        self.prev_raw = None
        self.prev_t = None
        self.zero_rows = []

    def cycle(self, iq_cmd, phase, step, next_t):
        r = self.rig
        st = r.torque(iq_cmd)
        tc = r.now()
        a = r.a92()
        rw = r.raw()
        if a is not None:
            self.last["a92"] = a
        self.last["raw"] = rw
        iq, dps, deg = st if st else ("", "", "")
        self.w.writerow(["cyc", f"{tc:.5f}", phase, step, iq_cmd, iq, dps, deg, "" if a is None else f"{a:.2f}", rw])
        # 안전 검사
        if st and abs(dps) > LIM_DPS:
            raise Abort(f"팔 속도 {dps} dps > {LIM_DPS}")
        if a is not None and abs(a - self.a_start) > LIM_DEG:
            raise Abort(f"시작 대비 {a - self.a_start:+.1f}° > {LIM_DEG}")
        if self.prev_raw is not None:
            da = ((rw - self.prev_raw + 2048) % 4096 - 2048) * 2 * math.pi / 4096
            if abs(da / max(1e-3, tc - self.prev_t)) > LIM_PEND:
                raise Abort("진자 속도 한계 초과")
        self.prev_raw, self.prev_t = rw, tc
        while time.perf_counter() - r.t0 < next_t - 0.0015:   # 남는 시간: AS5600 빠른 기록
            self.w.writerow(["fast", f"{r.now():.5f}", phase, step, "", "", "", "", "", r.raw()])
        while time.perf_counter() - r.t0 < next_t:
            pass
        return st, a, rw

    def pulse(self, iq, dur, phase, step):
        n = int(round(dur / DT))
        next_t = self.rig.now()
        for _ in range(n):
            next_t += DT
            self.cycle(iq, phase, step, next_t)

    def settle(self, phase, step):
        """iq 0 을 계속 보내며 팔·진자가 멈출 때까지. 멈추면 영점 표에 기록."""
        t_s = self.rig.now()
        hist = []                                    # (t, raw, dps)
        next_t = t_s
        settled = False
        while True:
            next_t += DT
            st, a, rw = self.cycle(0, phase + "_settle", step, next_t)
            t = self.rig.now()
            hist.append((t, rw, st[1] if st else 0))
            hist = [h for h in hist if h[0] > t - 0.5]
            el = t - t_s
            if el >= SETTLE_MIN_S and hist[0][0] < t - 0.45:
                raws = [h[1] for h in hist]
                if max(raws) - min(raws) <= STILL_RAW and all(h[2] == 0 for h in hist):
                    settled = True
                    break
            if el >= SETTLE_MAX_S:
                break
        raws = sorted(h[1] for h in hist)
        med = raws[len(raws) // 2]
        row = dict(phase=phase, step=step, t=round(self.rig.now(), 3), a92=self.last["a92"],
                   arm_mod360=None if self.last["a92"] is None else round(self.last["a92"] % 360.0, 2),
                   pend_raw=med, pend_spread=raws[-1] - raws[0], settled=settled, wait_s=round(self.rig.now() - t_s, 2))
        self.zero_rows.append(row)
        print(f"  [{phase} {step}] 정지 {'O' if settled else 'X(시간초과)'} {row['wait_s']} s, "
              f"0x92 {row['a92']:.2f}° (mod360 {row['arm_mod360']}), 진자 RAW {med} (변동 {row['pend_spread']})", flush=True)
        return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--go", action="store_true")
    a = ap.parse_args()
    stamp = session.stamp()
    base = os.path.join(session.LOGDIR, f"exp2b_highspeed_{stamp}")
    os.makedirs(session.LOGDIR, exist_ok=True)
    rig = Rig(base + "_can.csv")
    fh = open(base + ".csv", "w", newline="")
    w = csv.writer(fh)
    w.writerow(["kind", "t", "phase", "step", "iq_cmd", "iq", "dps", "deg_a1", "a92", "raw"])
    run = Runner(rig, w)
    started = False
    try:
        session.preflight(rig.bus, rig.i2c, "exp2b_highspeed")
        if not a.go:
            print("--go 없이 실행: 점검만 하고 끝냄")
            return
        started = True
        print("0x77 응답:", (rig.cmd(0x77) or b"").hex(" "))
        t0 = time.time()
        while True:
            d = rig.cmd(0x9A)
            if d is not None and d[3] == 1:
                print(f"브레이크 해제 확인 {time.time() - t0:.2f} s")
                break
            if time.time() - t0 > 3.0:
                raise Abort("3 s 안에 브레이크 해제 확인 안 됨")
            time.sleep(0.05)
        run.a_start = rig.a92()
        print(f"시작 0x92 {run.a_start:.2f}°")
        run.settle("start", 0)

        print("A. 식별 펄스")
        k = 0
        for lvl in ID_LEVELS:
            for sgn in (+1, -1):
                k += 1
                run.pulse(sgn * lvl, ID_PULSE_S, "id", k)
                run.settle("id", k)

        print("완료")
    except KeyboardInterrupt:
        print("Ctrl+C -> 정지")
    except (Abort, session.PreflightError, canguard.CanGuardError) as e:
        print("중단:", e)
    except Exception as e:
        print("예외:", repr(e))
    finally:
        if started:
            for c in (lambda: rig.torque(0), lambda: rig.cmd(0x81), lambda: rig.cmd(0x78)):
                for _ in range(3):
                    try:
                        c()
                    except Exception as e:
                        print("  정지 명령 중 오류(계속 시도):", e)
            print("종료: iq 0 -> 0x81 -> 0x78 전송")
            try:
                print("마지막 0x92 각도 저장:", session.record_end_angle(rig.bus))
            except Exception as e:
                print("마지막 각도 저장 실패:", e)
        fh.close()
        rig.close()
        if not started:                              # 점검만 했으면 빈 기록 파일 지움
            for suffix in (".csv", "_can.csv"):
                try:
                    os.remove(base + suffix)
                except OSError:
                    pass
        if run.zero_rows:
            with open(base + "_zero.csv", "w", newline="") as zf:
                zw = csv.DictWriter(zf, fieldnames=list(run.zero_rows[0].keys()))
                zw.writeheader()
                zw.writerows(run.zero_rows)
        if started:
            print("기록:", base + ".csv", "/ _can.csv / _zero.csv")


if __name__ == "__main__":
    main()
