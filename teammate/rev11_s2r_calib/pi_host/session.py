"""세션 시작 점검 / 종료 (이 실기는 Simulink 쪽 실험과 번갈아 쓴다).

  python session.py check            # 시작 점검만 (모터 명령 없음, 0x92·0x9A 읽기만)
  python session.py end              # 세션 종료: 마지막 0x92 각도 저장

모든 실험 스크립트는 CAN 명령을 보내기 전에 preflight() 를 부른다:
  1. can0 UP, ERROR-ACTIVE, 1 Mbps, 다른 CAN 송신 프로세스 없음 (아니면 중단: 상대방 종료 확인 후 사용자가 재설정)
  2. 1 s 동안 듣기만 해서 0x141/0x241 프레임이 보이면 다른 쪽이 쓰는 중 -> 중단
  3. 0x92 시작 각도 기록, 이전 세션(우리) 마지막 각도와 비교해 몇 바퀴 바뀌었는지 알림 (케이블 확인)
  4. 진자 정지 RAW 를 읽어 영점 2027 과 많이 다르면 알림 (재장착 여부 확인)
"""
import os
import sys
import json
import time
import argparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import canguard  # noqa: E402

REQ, RSP = 0x141, 0x241
ZERO_RAW = 2027              # (옛 고정 영점, 기록 스크립트의 참고용 α 계산에만 씀)
# 진자 영점(아래로 매달림 RAW)은 받침 기울기 때문에 팔 각도에 따라 바뀜. RAW0 = C + A·cos(θ − φ), θ = 0x92 각도[deg](mod 360).
# 2026-11-20 받침을 수평으로 바꾼 뒤(사용자) 다시 잼: logs/zero_sweep_20261120_020452_zero.csv 정지 16곳, 잔차 RMS 0.90카운트(최대 1.9).
#   남은 진폭 12.5카운트(≈1.1°). 백업 session.py.bak_20261120.
# (옛 값, 받침 약 2.5° 기울어진 상태, 실험 2 2026-11-18 17:41 정지 34곳: 2038.1, 28.2, 30.0)
# θ 는 모터가 준 0x92 각도 그대로다. 정책 관측용 θ_sim(= 0x92 − 시작 각도)과 섞지 말 것.
ZERO_C, ZERO_A, ZERO_PHI_DEG = 2034.2, 12.5, 136.0
ZERO_WARN_COUNTS = 10        # 식과 이만큼(0.9°) 넘게 다르면 알림 (진자 마찰 정지 범위 ±5 + 식 잔차)


def zero_raw(a92_deg):
    """팔 각도(0x92, deg)에서의 진자 영점 RAW. a92_deg 가 None 이면 평균 C."""
    import math as _m
    if a92_deg is None:
        return ZERO_C
    return ZERO_C + ZERO_A * _m.cos(_m.radians(a92_deg - ZERO_PHI_DEG))
STILL_COUNTS = 6             # 0.5 s 동안 이보다 크게 움직이면 "진자 흔들리는 중"
STATE = os.path.join(HERE, "state", "session_state.json")
LOGDIR = os.path.join(os.path.dirname(HERE), "logs")   # 패키지: 최상위 logs/


class PreflightError(RuntimeError):
    pass


def stamp():
    return time.strftime("%Y%m%d_%H%M%S")


def log_path(prefix, ext="csv"):
    """실험 기록 파일 이름: <prefix>_YYYYmmdd_HHMMSS.csv (상대방 실험 전후 기록이 섞이지 않게)."""
    os.makedirs(LOGDIR, exist_ok=True)
    return os.path.join(LOGDIR, f"{prefix}_{stamp()}.{ext}")


def load_state():
    try:
        with open(STATE) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def save_state(**kw):
    st = load_state()
    st.update(kw)
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE, "w") as fh:
        json.dump(st, fh, ensure_ascii=False, indent=1)
    return st


def _xfer(bus, cmd, payload=b"", timeout=0.03):
    import can
    d = bytearray(8)
    d[0] = cmd
    d[1:1 + len(payload)] = payload
    canguard.fast_check()
    while True:                      # 이전 명령의 늦은/중복 응답을 비움 (다른 송신자 검사는 유지)
        old = bus.recv(timeout=0.0)
        if old is None:
            break
        canguard.foreign_frame(old)
    bus.send(can.Message(arbitration_id=REQ, data=bytes(d), is_extended_id=False))
    end = time.time() + timeout
    wrong = None
    while time.time() < end:
        m = bus.recv(timeout=max(0.0, end - time.time()))
        if m is None:
            break
        canguard.foreign_frame(m)
        if m.arbitration_id == RSP:
            if m.data[0] == cmd:
                return bytes(m.data)
            wrong = bytes(m.data)
    if wrong is not None:
        raise PreflightError(f"모터가 0x{cmd:02X} 에 다른 명령의 응답을 줌: {wrong.hex(' ')} "
                             f"(마지막 응답을 반복하는 상태로 보임, 2026-11-18 두 번 발생). "
                             f"명령이 실행되는지도 알 수 없음 -> 48 V 를 뽑고 10 s 이상 뒤 재투입")
    return None


def read_a92(bus):
    d = _xfer(bus, 0x92)
    return None if d is None else int.from_bytes(d[4:8], "little", signed=True) * 0.01


def listen_only(bus, seconds=1.0):
    """송신 없이 듣기. 0x141/0x241 이 보이면 다른 쪽이 버스를 쓰는 중."""
    end = time.time() + seconds
    seen = {}
    while time.time() < end:
        m = bus.recv(timeout=max(0.0, end - time.time()))
        if m is not None:
            seen.setdefault(m.arbitration_id, bytes(m.data).hex(" "))
    ours = {k: v for k, v in seen.items() if k in (REQ, RSP)}
    if ours:
        raise PreflightError("다른 쪽이 모터 버스를 쓰는 중 (1 s 듣기에서 감지): " +
                             ", ".join(f"0x{k:03X} {v}" for k, v in ours.items()))
    return seen


def pend_rest(i2c, seconds=0.5):
    v = []
    end = time.time() + seconds
    while time.time() < end:
        hi, lo = i2c.read_i2c_block_data(0x36, 0x0C, 2)
        v.append(((hi & 0x0F) << 8) | lo)
        time.sleep(0.005)
    v.sort()
    return v[len(v) // 2], v[-1] - v[0]


def preflight(bus, i2c=None, label=""):
    """CAN 명령을 보내기 전에 호출. 중단 사유면 PreflightError/CanGuardError. 경고는 출력하고 dict 로 반환."""
    out = {"label": label, "time": time.strftime("%Y-%m-%d %H:%M:%S")}
    print("=== 세션 시작 점검", label)
    try:
        out["can0"] = canguard.full_check()
    except canguard.CanGuardError as e:
        raise PreflightError(f"can0 이상 -> 중단. 상대방 실험이 끝났는지 확인한 뒤 다시 설정하세요: {e}")
    print(" 1. can0:", out["can0"])
    seen = listen_only(bus, 1.0)
    print(" 2. 1 s 듣기: 0x141/0x241 없음" + (f" (기타 ID {[hex(k) for k in seen]})" if seen else ""))

    replies = {}
    for c in (0x9A, 0x92, 0x9C):     # 다른 명령의 응답이 오면 _xfer 가 PreflightError
        r = _xfer(bus, c)
        if r is None:
            raise PreflightError(f"0x{c:02X} 응답 없음")
        replies[c] = r
    print(f"    응답 확인: 0x9A/0x92/0x9C 각각 맞는 응답 (0x9A {replies[0x9A].hex(' ')}, 브레이크 {replies[0x9A][3]})")
    a92 = int.from_bytes(replies[0x92][4:8], "little", signed=True) * 0.01
    out["brake"] = replies[0x9A][3]
    st = load_state()
    out["a92_start"] = a92
    last = st.get("a92_last")
    if last is None:
        print(f" 3. 0x92 시작 {a92:.2f}° (이전 세션 기록 없음)")
    else:
        turns = (a92 - last) / 360.0
        within = (a92 - last + 180.0) % 360.0 - 180.0     # 한 바퀴 안의 차이
        out["turns_since_last"] = turns
        flag = "  <- 케이블 확인" if abs(turns) >= 0.5 else ""
        print(f" 3. 0x92 시작 {a92:.2f}°, 이전 세션 마지막 {last:.2f}° ({st.get('a92_last_time')}) "
              f"-> {turns:+.2f} 바퀴 (한 바퀴 안 차이 {within:+.1f}°){flag}")
        if abs(turns) >= 0.5 and abs(within) < 5.0 and abs(turns - round(turns)) < 0.02:
            print("    정수 바퀴만 차이: 모터 전원 재투입으로 다회전 카운트가 초기화됐을 수 있음"
                  "(한 바퀴 안 각도는 유지됨). 실제로 돌았는지 케이블로 확인.")

    if i2c is not None:
        med, spread = pend_rest(i2c)
        out["pend_raw"], out["pend_spread"] = med, spread
        z0 = zero_raw(a92)
        out["pend_zero_expected"] = z0
        msg = (f" 4. 진자 RAW {med}, 이 팔 각도({a92 % 360:.1f}°)의 영점 식 {z0:.1f} 대비 {med - z0:+.1f}, "
               f"0.5 s 변동 {spread}")
        if spread > STILL_COUNTS:
            msg += "  <- 진자가 흔들리는 중"
        elif abs(med - z0) > ZERO_WARN_COUNTS:
            msg += "  <- 영점과 많이 다름: 진자 재장착 여부 확인"
        print(msg)

    save_state(last_preflight=out)
    return out


def record_end_angle(bus):
    a = read_a92(bus)
    if a is not None:
        save_state(a92_last=a, a92_last_time=time.strftime("%Y-%m-%d %H:%M:%S"))
    return a


def open_bus():
    import can
    return can.interface.Bus(channel="can0", interface="socketcan")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["check", "end"])
    a = ap.parse_args()
    from smbus2 import SMBus
    bus, i2c = open_bus(), SMBus(1)
    try:
        if a.mode == "check":
            preflight(bus, i2c, "check")
        else:
            print("마지막 0x92 각도 저장:", record_end_angle(bus))
    except (PreflightError, canguard.CanGuardError) as e:
        print("중단:", e)
        raise SystemExit(1)
    finally:
        bus.shutdown()
        i2c.close()


if __name__ == "__main__":
    main()
