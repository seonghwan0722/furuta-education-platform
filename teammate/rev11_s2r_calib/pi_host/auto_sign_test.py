"""부호 자동 판정 시험 (모터 사용). 실행 전 사용자 확인 필수.

순서
  0. can0 전체 점검(UP, ERROR-ACTIVE, 1 Mbps, 다른 CAN 송신 프로세스 없음)
  2. 0x77 브레이크 해제 -> 0x9A DATA[3]==1 될 때까지 대기(최대 3 s, 안 되면 중단)
  3. iq +60 (0.6 A) 을 0.2 s 동안 20 ms마다 송신. 매 주기 0xA1 응답(각도 1°, 속도 dps, iq), 0x92, AS5600 기록.
     주기 사이에는 AS5600 만 빠르게(약 2 ms 간격) 추가 기록 -> α 초기 방향 판정용.
  4. iq 0 -> 0x81 정지 -> 300 ms 동안 AS5600 계속 기록 -> 0x78 잠금 -> 0x9A 브레이크 00 확인
  예외·Ctrl+C·can0 이상 시에도 finally 에서 iq 0 -> 0x81 -> 0x78.

판정
  (a) 0x92 변화 > 0 이고, 펄스 구간의 0xA1 각도 변화 및 속도 적분과 일치(0x92 = 0.01°/LSB 확인)
  (b) 펄스 시작 뒤 α(alpha_sign=+1, 영점 2027)가 처음 음수 -> alpha_sign=+1, 양수 -> -1
      (모델 관성으로 계산: 정지·α=0에서 α̈ = -0.62 θ̈, 즉 +τ 이면 α 가 먼저 음수)

  python auto_sign_test.py --go
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
IQ_PULSE = 60            # 0.01 A 단위 -> 0.6 A
IQ_HARD_MAX = 80         # 코드 상한 0.8 A
PULSE_S = 0.20
DT = 0.020
SILENCE_S = 0.30
OFFSET_RAW = 2027
ABORT_DEG = 150.0        # 펄스 중 0x92 변화가 이보다 크면 즉시 iq 0
ABORT_DPS = 1200


class Rig:
    def __init__(self):
        import can
        from smbus2 import SMBus
        self.can = can
        self.bus = can.interface.Bus(channel="can0", interface="socketcan")
        self.i2c = SMBus(1)

    def close(self):
        try:
            self.bus.shutdown()
        finally:
            self.i2c.close()

    def raw(self):
        hi, lo = self.i2c.read_i2c_block_data(0x36, 0x0C, 2)
        return ((hi & 0x0F) << 8) | lo

    def send(self, data8):
        canguard.fast_check()
        self.bus.send(self.can.Message(arbitration_id=REQ, data=bytes(data8), is_extended_id=False))

    def xfer(self, cmd, payload=b"", timeout=0.03):
        d = bytearray(8)
        d[0] = cmd
        d[1:1 + len(payload)] = payload
        self.send(d)
        deadline = time.time() + timeout
        while time.time() < deadline:
            m = self.bus.recv(timeout=max(0.0, deadline - time.time()))
            if m is None:
                break
            canguard.foreign_frame(m)
            if m.arbitration_id == RSP and m.data[0] == cmd:
                return bytes(m.data)
        return None

    def drain(self, seconds):
        """송신 없이 수신만 감시(다른 송신자 감지)."""
        end = time.time() + seconds
        while time.time() < end:
            m = self.bus.recv(timeout=max(0.0, end - time.time()))
            if m is not None:
                canguard.foreign_frame(m)

    # --- 명령 ---
    def torque(self, iq):
        iq = max(-IQ_HARD_MAX, min(IQ_HARD_MAX, int(iq)))
        v = iq & 0xFFFF
        d = self.xfer(0xA1, bytes([0, 0, 0, v & 0xFF, v >> 8]))
        if d is None:
            return None
        return dict(iq=int.from_bytes(d[2:4], "little", signed=True),
                    dps=int.from_bytes(d[4:6], "little", signed=True),
                    deg=int.from_bytes(d[6:8], "little", signed=True))

    def a92(self):
        d = self.xfer(0x92)
        return None if d is None else int.from_bytes(d[4:8], "little", signed=True) * 0.01

    def st9a(self):
        return self.xfer(0x9A)

    def st9c(self):
        d = self.xfer(0x9C)
        if d is None:
            return None
        return dict(iq=int.from_bytes(d[2:4], "little", signed=True),
                    dps=int.from_bytes(d[4:6], "little", signed=True),
                    deg=int.from_bytes(d[6:8], "little", signed=True), raw=d.hex(" "))


def alpha_of(raw):
    a = (raw - OFFSET_RAW) * 2 * math.pi / 4096
    return (a + math.pi) % (2 * math.pi) - math.pi


def safe_stop(rig):
    for fn in (lambda: rig.torque(0), lambda: rig.xfer(0x81), lambda: rig.xfer(0x78)):
        for _ in range(2):
            try:
                fn()
            except Exception as e:  # can0 이 꺼졌어도 나머지는 시도
                print("  정지 명령 실패:", e)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--go", action="store_true", help="실제로 모터를 움직인다")
    ap.add_argument("--iq", type=int, default=IQ_PULSE, help="펄스 iq (0.01 A), ±60 등. 부호 반대 확인용")
    ap.add_argument("--log", default=None)
    a = ap.parse_args()
    if not (0 < abs(a.iq) <= IQ_HARD_MAX):
        ap.error(f"|iq| 는 1..{IQ_HARD_MAX}")
    iq_pulse = a.iq
    a.log = a.log or session.log_path(f"auto_sign_iq{iq_pulse:+d}")

    rig = Rig()
    try:
        session.preflight(rig.bus, rig.i2c, "auto_sign_test")
    except (session.PreflightError, canguard.CanGuardError) as e:
        rig.close()
        print("중단(모터 명령 보내지 않음):", e)
        raise SystemExit(1)
    if not a.go:
        rig.close()
        print("--go 없이 실행: 점검만 하고 끝냄")
        return

    cyc, fast, notes = [], [], {}
    raw0 = a92_0 = None
    try:

        # 2. 브레이크 해제 대기
        print("0x77 응답:", (rig.xfer(0x77) or b"").hex(" "))
        t0 = time.time()
        while True:
            d = rig.st9a()
            if d is not None and d[3] == 1:
                notes["brake_release_s"] = time.time() - t0
                print(f"브레이크 해제 확인 {notes['brake_release_s']*1000:.0f} ms ({d.hex(' ')})")
                break
            if time.time() - t0 > 3.0:
                raise RuntimeError(f"3 s 안에 브레이크 바이트가 01 이 안 됨 (마지막 0x9A {d.hex(' ') if d else None})")
            time.sleep(0.05)

        # 기준값
        raw0 = sorted(rig.raw() for _ in range(21))[10]
        a92_0 = rig.a92()
        s9c0 = rig.st9c()
        print(f"기준: 0x92 {a92_0:.2f}°, 0x9C 각도 {s9c0['deg']}°, AS5600 raw {raw0}")

        # 3. 펄스
        tp = time.time()
        next_t = tp
        for k in range(int(round(PULSE_S / DT))):
            st = rig.torque(iq_pulse)
            tc = time.time() - tp
            ang = rig.a92()
            rw = rig.raw()
            cyc.append(dict(t=tc, iq_cmd=iq_pulse, **(st or dict(iq=None, dps=None, deg=None)), a92=ang, raw=rw))
            if st is None or ang is None:
                raise RuntimeError(f"펄스 {k}: 모터 응답 없음")
            if abs(ang - a92_0) > ABORT_DEG or abs(st["dps"]) > ABORT_DPS:
                notes["aborted"] = f"k={k}, Δ0x92={ang - a92_0:.1f}°, {st['dps']} dps"
                print("안전 한계 도달, 펄스 중단:", notes["aborted"])
                break
            canguard.fast_check()
            next_t += DT
            while time.time() < next_t:
                fast.append((time.time() - tp, rig.raw()))
                time.sleep(0.002)

        # 4. iq 0 -> 송신 중단
        st = rig.torque(0)
        tc = time.time() - tp
        ang_end = rig.a92()
        cyc.append(dict(t=tc, iq_cmd=0, **(st or dict(iq=None, dps=None, deg=None)), a92=ang_end, raw=rig.raw()))
        rig.xfer(0x81)
        ts = time.time()
        while time.time() - ts < SILENCE_S:
            fast.append((time.time() - tp, rig.raw()))
            rig.drain(0.002)
        notes["a92_final"] = rig.a92()
        rig.xfer(0x78)
        time.sleep(0.1)
        d = rig.st9a()
        notes["brake_after_lock"] = d[3] if d else None
        print("정지·잠금 완료. 0x9A:", d.hex(" ") if d else None)
    except KeyboardInterrupt:
        print("Ctrl+C")
    except Exception as e:
        print("중단:", e)
        notes["error"] = str(e)
    finally:
        safe_stop(rig)
        try:
            print("마지막 0x92 각도 저장:", session.record_end_angle(rig.bus))
        except Exception as e:
            print("마지막 각도 저장 실패:", e)
        rig.close()
        print("finally: iq 0 -> 0x81 -> 0x78 전송")
        with open(a.log, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["kind", "t", "iq_cmd", "iq", "dps", "deg_a1", "a92", "raw"])
            for c in cyc:
                w.writerow(["cyc", f"{c['t']:.4f}", c["iq_cmd"], c["iq"], c["dps"], c["deg"], c["a92"], c["raw"]])
            for t, rw in fast:
                w.writerow(["fast", f"{t:.4f}", "", "", "", "", "", rw])
        print("로그:", a.log)

    analyse(cyc, fast, notes, raw0, a92_0, iq_pulse)


def analyse(cyc, fast, notes, raw0, a92_0, iq_pulse):
    sgn_iq = 1 if iq_pulse > 0 else -1
    print("\n=== 판정 ===")
    for k, v in notes.items():
        print(f"  {k}: {v}")
    good = [c for c in cyc if c["iq"] is not None]
    if len(good) < 2 or raw0 is None:
        print("데이터 부족: 판정 불가")
        return
    # (a)
    d92 = good[-1]["a92"] - good[0]["a92"]
    da1 = good[-1]["deg"] - good[0]["deg"]
    integ = sum(0.5 * (good[i]["dps"] + good[i + 1]["dps"]) * (good[i + 1]["t"] - good[i]["t"])
                for i in range(len(good) - 1))
    tot = (notes.get("a92_final") or good[-1]["a92"]) - a92_0
    print(f"(a) 펄스 구간: Δ0x92 {d92:+.2f}°, Δ0xA1각도 {da1:+d}°, ∫속도 {integ:+.1f}°  | 전체 Δ0x92 {tot:+.2f}°")
    print(f"    응답 iq: {[c['iq'] for c in good]}")
    print(f"    속도 dps: {[c['dps'] for c in good]}")
    ok_sign = d92 * sgn_iq > 0
    ok_scale = abs(d92 - da1) <= 2.0 and abs(d92 - integ) <= max(3.0, 0.2 * abs(d92))
    p = [c["iq"] for c in good if c["iq_cmd"] == iq_pulse]
    if len(p) > 1:
        print(f"    응답 iq(펄스, 첫 값 제외): min {min(p[1:])} max {max(p[1:])} 평균 {sum(p[1:])/len(p[1:]):.1f} / 명령 {iq_pulse}")
    print(f"    -> 0x92 변화 부호가 iq 와 같음: {'예' if ok_sign else '아니오'}, 0.01°/LSB 일치: {'예' if ok_scale else '확인 필요'}")
    # (b)
    seq = sorted([(c["t"], c["raw"]) for c in cyc] + fast)
    first = next(((t, rw - raw0) for t, rw in seq if abs(rw - raw0) >= 4), None)
    if first is None:
        print("(b) α 변화 4카운트(0.35°) 미만: 판정 불가")
        return
    t, dr = first
    amin = min(alpha_of(rw) for _, rw in seq)
    amax = max(alpha_of(rw) for _, rw in seq)
    print(f"(b) 첫 변화 t={t*1000:.0f} ms, Δraw {dr:+d} (α(+1) {math.degrees(dr*2*math.pi/4096):+.2f}°), "
          f"α 범위 {math.degrees(amin):+.1f}° ~ {math.degrees(amax):+.1f}°")
    # 시뮬: +τ 이면 α 가 먼저 음수. 즉 α(+1) 첫 변화 부호가 iq 와 반대면 alpha_sign=+1
    sign = +1 if dr * sgn_iq < 0 else -1
    print(f"    -> alpha_sign = {sign:+d}")


if __name__ == "__main__":
    main()
