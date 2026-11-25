"""팀원 정책(sac_rev11)을 Pi에서 실기 Furuta 에 올리는 호스트.

구성
- 팔 모터: RMD-X6 (CAN, can0 1 Mbps). 0xA1 토크 명령 한 번에 응답(온도, iq, 속도, 각도)이 옵니다.
- 진자: AS5600 (I2C 0x36), RAW ANGLE 12비트.
- 정책: actor_rev11.npz (numpy 추론, policy_np.py).

부호 규약 (2026-11-18 변경)
- 시뮬 동역학이 좌우 대칭(M00, M01 짝함수, G1 홀함수)이라 회전 방향 이름은 필요 없다.
- θ_sim = +(0x92 각도 - 시작 각도), θ̇_sim = +속도, τ_sim = +iq 방향 (반전 없음).
- alpha_sign 은 auto_sign_test.py 로 정한다(+iq 펄스 직후 α 가 음수면 +1).

토크 -> 전류 (미확정 값은 CONFIG 에서 바꿉니다)
- I = τ_real / KT + I0*sign(τ_real),  iq = round(I / 0.01)
- KT: 데이터시트 2.1 N·m/A (차트 2.65 는 입력 직류 전류 기준이라 쓰지 않음).
- 시뮬과 같은 속도-토크 제한: 구동 방향이면 |τ| ≤ τ_max(1 − |θ̇|/16), 제동은 전토크.
- I0: 0 (기본). 정지 시험 결과에 따라 조정.

브리지 보상 (c) (--comp, 2026-11-18): 정책 실행 바로 전에 같은 조건에서 마찰을 다시 재고 그 값으로 보상.
- 2026-11-20 기본 동작: logs/kit_params_latest.json 이 valid·30분 이내·현재 온도 ±3°C 면 그 bridge 값으로 펄스 생략,
  아니면 재측정 → 정책 뒤 quick_id 로 MuJoCo 용 값까지 계산해 kit_params_<시각>.json·latest 저장.
  --fric-file 로 다른 파일, --fresh-measure 로 무조건 재측정. 예전 동작 = --fresh-measure --no-brake-limit.
- 마찰 재측정: ±fric_levels 펄스(각 fric_pulse_s), 마지막 fric_window_s 의 평균으로 iq×Kt − J·ω̇ = Fc± + b·|θ̇| 최소제곱.
- τ_cmd = s·τ_pol + (Fc± − 0.012)·tanh(θ̇/0.2) + (b − 1e-4)·θ̇,  τ_pol = speed_torque_limit(u·τmax) (학습 환경과 같은 순서),
  s = (comp_J + 몸체 2.358e-4)/5.2358e-3. 보상은 학습 조건 마찰(쿨롱 0.012, 점성 1e-4)을 뺀 차이만.
종료: iq 0 을 10 ms 마다 보내며 팔 속도 < 50 dps (최대 1 s) -> 0x81 정지 -> 0x78 브레이크
  -> 0x9C 로 팔 속도 < 50 dps 다시 확인되면 0x80 출력 끄기 (2026-11-20 추가: 대기 중 MOS 발열 대책).

제동 전력 제한 (--brake-plim W --brake-zone-deg Z, 2026-11-20, 기본 켬 5 W·20°, --no-brake-limit 로 끔): 고속 급제동 직후 모터 전원이 끊긴 일(회생 가설) 대응.
- 제동 = 최종 명령 토크 τ_cmd 와 팔 속도 θ̇(직전 응답) 의 부호가 반대, 제동 전력 P = |τ_cmd·θ̇|.
- 직립에서 벗어난 각 |wrap(α − π)| > Z 이고 제동이면 |τ_cmd| ≤ P_lim/|θ̇|. 직립 구간(≤ Z)은 제한 없음.
- 순서: τ_cmd(보상 포함) → iq 상한 → 제동 제한 → iq. 시뮬 sim/eval_brake_limit.py 와 같은 순서.
상태 1 기록 (--log-voltage): 매 주기 0xA1·0x92 뒤 0x9A 를 한 번 더 읽어 응답 8바이트를 hex 그대로 기록(st1_hex, 해석은 분석 때).

사용법
  python run_policy.py --dry-run                       # 모터 명령 없이 센서/관측/정책 출력만 확인
  python run_policy.py --run --tau 1.0                 # 보상 없이 (iq 상한 60)
  python run_policy.py --run --tau 1.0 --comp --iq-max 120   # 마찰 재측정 + 보상 (c), iq 상한 1.2 A
"""
import os
import sys
import csv
import math
import time
import argparse

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from policy_np import ActorNP  # noqa: E402
import canguard  # noqa: E402
import session  # noqa: E402
import kitparams  # noqa: E402

CONFIG = dict(
    can_channel="can0",
    motor_id=1,              # 0x141 요청 / 0x241 응답
    dt=0.020,                # 50 Hz
    watchdog=0.100,          # 이 시간 넘게 응답이 없으면 정지
    KT=2.1,                  # N·m/A, 데이터시트 초기값 (차트 2.65 는 입력 직류 전류 기준이라 틀림)
    w_no_load=16.0,          # rad/s, 시뮬 furuta_env 의 속도-토크 제한 (arm_no_load_speed)
    I0=0.0,                  # A (정지 시험 후 조정)
    IQ_MAX=60,               # 기본 iq 상한 (0.01 A). --iq-max 로 바꿈 (IQ_HARD_MAX 이하)
    IQ_HARD_MAX=180,         # 코드 절대 상한 1.8 A
    alpha_sign=+1,           # auto_sign_test 2026-11-18 16:39: +iq 펄스 직후 α 음수 -> +1
    # 진자 영점: session.zero_raw(0x92 각도) = 2034.2 + 12.5·cos(θ − 136°) (2026-11-20 받침 수평 뒤 재측정, zero_sweep_20261120_020452).
    # θ 는 0x92 각도 그대로이고 정책 관측용 θ_sim 과 다르다.
    # 팔 회전 각도 한계 없음 (슬립링, 사용자 확인 2026-11-18)
    arm_speed_limit_dps=1100,  # 팔 속도 한계 (마찰 측정 범위 위로는 가지 않게)
    stop_speed_dps=50,       # 종료 시 이 속도 아래가 되면 정지·브레이크
    stop_wait_s=1.0,         # 그때까지 최대 대기
    # 브리지 보상 (c)
    comp_J=0.0232,           # 관성 배율에 쓰는 팔 armature (실험 2 최종)
    J_body=2.358e-4,         # 팔+진자 몸체 관성(α=0)
    J_train_total=5.2358e-3, # 학습 조건 팔 축 관성
    comp_eps=0.2,            # 쿨롱 보상 tanh 폭 [rad/s]
    train_fc=0.012, train_b=1e-4,
    fric_levels=[60, 80, 100],   # 마찰 재측정 펄스 iq (0.01 A), 양방향
    fric_pulse_s=0.8,        # 펄스 길이 (시정수 0.1~0.2 s 의 4~8 배)
    fric_window_s=0.2,       # 펄스 끝 일정 속도 평균 구간
    pend_settle_max_s=40.0,  # 재측정 뒤 진자 정지 대기 최대
    pend_speed_limit=25.0,   # rad/s, 넘으면 정지
)

AS5600_ADDR = 0x36
AS5600_ANGLE_REG = 0x0C      # RAW ANGLE 상위 바이트, 12비트


def wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


class Pendulum:
    """AS5600 에서 진자 각도 α (rad). 아래 = 0, 도립 = π (시뮬 규약)."""

    def __init__(self, cfg):
        from smbus2 import SMBus
        self.bus = SMBus(1)
        self.cfg = cfg
        self.prev_a = None
        self.prev_t = None

    def read_alpha(self, t, a92_deg):
        """a92_deg: 모터 0x92 각도[deg] 그대로(영점 식의 θ). None 이면(dry-run) 영점 평균 session.ZERO_C 사용."""
        hi, lo = self.bus.read_i2c_block_data(AS5600_ADDR, AS5600_ANGLE_REG, 2)
        raw = ((hi & 0x0F) << 8) | lo
        self.last_raw = raw
        self.last_zero = session.zero_raw(a92_deg)
        ang = raw * 2 * math.pi / 4096.0
        off_rad = self.last_zero * 2 * math.pi / 4096.0
        sgn = self.cfg["alpha_sign"] if self.cfg["alpha_sign"] is not None else +1
        a = wrap(sgn * (ang - off_rad))
        ad = 0.0
        if self.prev_a is not None and t > self.prev_t:
            ad = wrap(a - self.prev_a) / (t - self.prev_t)
        self.prev_a, self.prev_t = a, t
        return a, ad


class Motor:
    """RMD-X6 0xA1 토크 명령. 응답에서 온도, iq, 속도(dps), 각도(°)를 읽습니다."""

    def __init__(self, cfg):
        import can
        self.bus = can.interface.Bus(channel=cfg["can_channel"], interface="socketcan")
        self.cfg = cfg
        self.req = 0x140 + cfg["motor_id"]
        self.rsp = 0x240 + cfg["motor_id"]

    def _send(self, data):
        import can
        canguard.fast_check()
        while True:                    # 늦게 온 이전 응답을 비움 (지금 명령의 응답으로 착각하지 않게)
            old = self.bus.recv(timeout=0.0)
            if old is None:
                break
            canguard.foreign_frame(old)
        self.bus.send(can.Message(arbitration_id=self.req, data=bytes(data), is_extended_id=False))

    def read_angle92(self, timeout=0.02):
        """0x92 다회전 각도 [deg], 0.01°/LSB."""
        self._send(bytes([0x92, 0, 0, 0, 0, 0, 0, 0]))
        deadline = time.time() + timeout
        while time.time() < deadline:
            m = self.bus.recv(timeout=max(0.0, deadline - time.time()))
            if m is None:
                break
            canguard.foreign_frame(m)
            if m.arbitration_id == self.rsp:
                if m.data[0] == 0x92:
                    return int.from_bytes(m.data[4:8], "little", signed=True) * 0.01
                raise RuntimeError(f"0x92 에 다른 명령의 응답 {bytes(m.data).hex(' ')} (응답 반복 상태) -> 중단")
        return None

    def send_torque(self, iq, timeout=0.05):
        import can
        data = bytearray(8)
        data[0] = 0xA1
        iq16 = int(iq) & 0xFFFF
        data[4] = iq16 & 0xFF
        data[5] = iq16 >> 8
        self._send(data)
        deadline = time.time() + timeout
        while time.time() < deadline:
            m = self.bus.recv(timeout=max(0.0, deadline - time.time()))
            if m is None:
                break
            canguard.foreign_frame(m)
            if m.arbitration_id == self.rsp and m.data[0] != 0xA1:
                raise RuntimeError(f"0xA1 에 다른 명령의 응답 {bytes(m.data).hex(' ')} (응답 반복 상태) -> 중단")
            if m.arbitration_id == self.rsp and m.data[0] == 0xA1:
                d = m.data
                iq_r = int.from_bytes(d[2:4], "little", signed=True)
                spd = int.from_bytes(d[4:6], "little", signed=True)     # dps
                ang = int.from_bytes(d[6:8], "little", signed=True)     # deg (1 LSB = 1°)
                return dict(temp=d[1], iq=iq_r, speed_dps=spd, angle_deg=ang)
        return None

    def send_stop(self):
        self._send(bytes([0x81, 0, 0, 0, 0, 0, 0, 0]))

    def send_brake_release(self):
        self._send(bytes([0x77, 0, 0, 0, 0, 0, 0, 0]))

    def xfer(self, data, timeout=0.03):
        self._send(data)
        deadline = time.time() + timeout
        while time.time() < deadline:
            m = self.bus.recv(timeout=max(0.0, deadline - time.time()))
            if m is None:
                break
            canguard.foreign_frame(m)
            if m.arbitration_id == self.rsp and m.data[0] == data[0]:
                return bytes(m.data)
        return None

    def wait_brake_released(self, timeout=3.0):
        """0x77 뒤 0x9A DATA[3]==1 될 때까지 대기 (실측 1.87 s 걸림)."""
        t0 = time.time()
        while time.time() - t0 < timeout:
            d = self.xfer(bytes([0x9A, 0, 0, 0, 0, 0, 0, 0]))
            if d is not None and d[3] == 1:
                return time.time() - t0
            time.sleep(0.05)
        raise RuntimeError("브레이크 해제 확인 실패 (0x9A DATA[3] != 1)")

    def shutdown(self):
        self.bus.shutdown()

    def send_brake_lock(self):
        self._send(bytes([0x78, 0, 0, 0, 0, 0, 0, 0]))

    def send_off(self):
        """0x80 모터 출력 끄기(V4.01 2.17.1, 운전 상태 지움). graceful_stop 이 0x78 뒤 속도 확인 후에만 씀."""
        self._send(bytes([0x80, 0, 0, 0, 0, 0, 0, 0]))


def speed_torque_limit(tau, w, tau_max, w0):
    """furuta_env._motor 와 같은 제한. tau, w 는 시뮬 부호."""
    if w0 > 0.0 and tau * w > 0.0:
        lim = tau_max * max(0.0, 1.0 - abs(w) / w0)
        return max(-lim, min(lim, tau))
    return tau


def brake_limit(tau, w, phi, plim, zone_rad):
    """제동 전력 제한. tau: 최종 명령 토크[N·m], w: 팔 속도[rad/s], phi: 직립에서 벗어난 각[rad]. plim None 이면 그대로."""
    if plim is None or abs(phi) <= zone_rad or tau * w >= 0.0 or w == 0.0:
        return tau
    lim = plim / abs(w)
    return max(-lim, min(lim, tau))


def graceful_stop(motor, cfg):
    """iq 0 을 10 ms 마다 보내며 팔 속도가 stop_speed_dps 아래가 되면(최대 stop_wait_s) 0x81 -> 0x78."""
    t0 = time.time()
    last = None
    try:
        while time.time() - t0 < cfg["stop_wait_s"]:
            st = motor.send_torque(0, timeout=0.01)
            if st is not None:
                last = st["speed_dps"]
                if abs(last) < cfg["stop_speed_dps"]:
                    break
            time.sleep(0.008)
    except Exception as e:
        print("종료 중 iq 0 송신 오류(정지·브레이크는 계속 보냄):", e)
    for fn in (motor.send_stop, motor.send_brake_lock):
        for _ in range(3):
            try:
                fn()
            except Exception as e:
                print("정지 명령 실패:", e)
    # 0x80(모터 출력 끄기): 0x78 뒤 0x9C 로 팔 속도 < stop_speed_dps 를 다시 확인한 경우에만 (2026-11-20, 대기 중 MOS 발열 대책)
    off = "0x80 안 보냄"
    try:
        time.sleep(0.02)
        d = motor.xfer(bytes([0x9C, 0, 0, 0, 0, 0, 0, 0]))
        if d is None:
            off = "0x80 안 보냄(0x9C 응답 없음)"
        else:
            spd = int.from_bytes(d[4:6], "little", signed=True)
            if abs(spd) < cfg["stop_speed_dps"]:
                for _ in range(3):
                    motor.send_off()
                off = f"0x80 (0x9C 속도 {spd} dps 확인)"
            else:
                off = f"0x80 안 보냄(0x9C 속도 {spd} dps ≥ {cfg['stop_speed_dps']})"
    except Exception as e:
        off = f"0x80 안 보냄({e})"
    print(f"종료: iq 0 {time.time() - t0:.2f} s (마지막 속도 {last} dps) -> 0x81 -> 0x78 -> {off}")


def measure_friction(motor, pend, cfg, iq_max, frows):
    """양방향 펄스로 일정 속도 구간의 iq×Kt = Fc± + b·|θ̇| 을 최소제곱으로 맞춤. 비정상이면 RuntimeError."""
    t0 = time.time()
    pts = []
    for lvl in [x for x in cfg["fric_levels"] if x <= iq_max]:
        for sgn in (+1, -1):
            seg = []
            ts = time.time()
            nt = ts
            while time.time() - ts < cfg["fric_pulse_s"]:
                nt += 0.01
                st = motor.send_torque(sgn * lvl)
                if st is None:
                    raise RuntimeError("마찰 측정 중 응답 없음")
                tt = time.time() - ts
                seg.append((tt, st["iq"], st["speed_dps"], st["temp"]))
                frows.append([round(time.time() - t0, 4), sgn * lvl, st["iq"], st["speed_dps"], st["temp"], pend_raw_now(pend)])
                if abs(st["speed_dps"]) > cfg["arm_speed_limit_dps"]:
                    raise RuntimeError(f"마찰 측정 중 팔 속도 한계 초과 {st['speed_dps']} dps")
                while time.time() < nt:
                    pass
            # iq 0 으로 팔이 멈출 때까지 (속도 0 이 0.2 s, 최대 2 s)
            ts2 = time.time()
            zero_since = None
            while time.time() - ts2 < 2.0:
                st = motor.send_torque(0)
                if st is not None:
                    frows.append([round(time.time() - t0, 4), 0, st["iq"], st["speed_dps"], st["temp"], pend_raw_now(pend)])
                    if abs(st["speed_dps"]) == 0:
                        zero_since = zero_since or time.time()
                        if time.time() - zero_since > 0.2:
                            break
                    else:
                        zero_since = None
                time.sleep(0.01)
            win = [x for x in seg if x[0] >= cfg["fric_pulse_s"] - cfg["fric_window_s"]]
            w_mean = math.radians(np.mean([x[2] for x in win]))
            w_first, w_last = win[0][2], win[-1][2]
            tw = np.array([x[0] for x in win])
            acc = np.polyfit(tw, np.radians([x[2] for x in win]), 1)[0]          # 구간 평균 가속도 [rad/s²]
            tau = np.mean([x[1] for x in win]) * 0.01 * cfg["KT"] - cfg["comp_J"] * acc   # 남은 가속 토크 J·ω̇ 를 뺌
            steady = abs(w_last - w_first) / max(1.0, abs(w_last))
            pts.append(dict(iq_cmd=sgn * lvl, tau=float(tau), w=float(w_mean), steady_change=float(steady),
                            temp=int(np.mean([x[3] for x in win]))))
            print(f"  마찰 펄스 iq {sgn * lvl:+4d}: 일정 구간 τ {tau:+.3f} N·m, 속도 {math.degrees(w_mean):+6.0f} dps, "
                  f"구간 속도 변화 {steady * 100:.1f}%, 모터 {pts[-1]['temp']}°C", flush=True)
    A, y = [], []
    for p in pts:
        A.append([1.0 if p["w"] > 0 else 0.0, 1.0 if p["w"] < 0 else 0.0, abs(p["w"])])
        y.append(abs(p["tau"]))
    (Fp, Fm, b), *_ = np.linalg.lstsq(np.array(A), np.array(y), rcond=None)
    res = np.array(y) - np.array(A) @ [Fp, Fm, b]
    out = dict(Fc_pos=float(Fp), Fc_neg=float(Fm), viscous=float(b), resid_rms=float(np.sqrt(np.mean(res ** 2))),
               points=pts, seconds=round(time.time() - t0, 1))
    measure_friction.last = out        # kit_identify 가 결과 비정상(예외)이어도 값을 남기려고 씀
    print(f"마찰 재측정 {out['seconds']} s: Fc+ {Fp:.3f}, Fc− {Fm:.3f} N·m, 점성 {b:.4f} N·m·s/rad, 잔차 {out['resid_rms']:.3f} N·m")
    bad = [k for k, v in (("Fc+", Fp), ("Fc−", Fm)) if not 0.05 <= v <= 1.5] + ([] if 0.0 <= b <= 0.6 else ["점성"])
    if bad or max(p["steady_change"] for p in pts) > 0.15:
        raise RuntimeError(f"마찰 재측정 결과 비정상({bad}, 최대 구간 속도 변화 "
                           f"{max(p['steady_change'] for p in pts) * 100:.0f}%) -> 정책 실행 안 함")
    return out


SETTLE_LOG = []     # 정지 대기 중 진자 RAW (t, raw) -> <기록>_settle.csv


def pend_raw_now(pend):
    hi, lo = pend.bus.read_i2c_block_data(AS5600_ADDR, AS5600_ANGLE_REG, 2)
    return ((hi & 0x0F) << 8) | lo


def wait_pendulum_still(pend, cfg, spread_max=6, settle_deg=None):
    """0.5 s 동안 진자 RAW 의 (최대−최소) ≤ spread_max 카운트면 정지로 봄.
    settle_deg 를 주면 기준을 '0.5 s 동안 진폭 (최대−최소)/2 ≤ settle_deg [°]' 로 바꿈."""
    if settle_deg is not None:
        spread_max = 2.0 * settle_deg * 4096.0 / 360.0
    t0 = time.time()
    while time.time() - t0 < cfg["pend_settle_max_s"]:
        v = []
        t1 = time.time()
        while time.time() - t1 < 0.5:
            hi, lo = pend.bus.read_i2c_block_data(AS5600_ADDR, AS5600_ANGLE_REG, 2)
            v.append(((hi & 0x0F) << 8) | lo)
            SETTLE_LOG.append((round(time.time() - t0, 4), v[-1]))
            time.sleep(0.005)
        if max(v) - min(v) <= spread_max:
            return time.time() - t0
    raise RuntimeError(f"진자가 {cfg['pend_settle_max_s']:.0f} s 안에 멈추지 않음 -> 정책 실행 안 함")


def torque_to_iq(tau_real, cfg):
    I = tau_real / cfg["KT"] + cfg["I0"] * (1.0 if tau_real > 0 else -1.0 if tau_real < 0 else 0.0)
    iq = int(round(I / 0.01))
    lim = cfg["IQ_MAX"]
    return max(-lim, min(lim, iq))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", default=os.path.join(HERE, "actor_rev11.npz"))
    ap.add_argument("--tau", type=float, default=0.3, help="정책 토크 한계 [N·m]")
    ap.add_argument("--seconds", type=float, default=10.0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--delay-test", action="store_true", help="모터에 토크 0 명령을 100회 보내 왕복 지연 측정")
    ap.add_argument("--log", default=None, help="기본: logs/run_policy_YYYYmmdd_HHMMSS.csv")
    ap.add_argument("--iq-max", type=int, default=CONFIG["IQ_MAX"], help="iq 상한 (0.01 A), 최대 IQ_HARD_MAX")
    ap.add_argument("--comp", action="store_true",
                    help="브리지 보상 (c). 마찰값은 logs/kit_params_latest.json 을 조건이 맞으면 재사용, 아니면 재측정")
    ap.add_argument("--fresh-measure", action="store_true", help="--comp 에서 파일이 있어도 무조건 재측정")
    ap.add_argument("--brake-plim", type=float, default=5.0,
                    help="스윙업 구간 제동 전력 상한 [W] (기본 5, 끄려면 --no-brake-limit)")
    ap.add_argument("--brake-zone-deg", type=float, default=20.0,
                    help="직립에서 이 각도 안은 제동 제한 없음 [deg] (기본 20)")
    ap.add_argument("--no-brake-limit", action="store_true", help="제동 전력 제한 끄기 (비교 시험용)")
    ap.add_argument("--log-voltage", action="store_true", help="매 주기 0x9A 상태 1 응답을 hex 로 기록")
    ap.add_argument("--fric-file", default=None,
                    help="--comp 와 함께: 기본 logs/kit_params_latest.json 대신 이 파일 사용 "
                         "(온도차 > 3°C, 30분 초과, invalid 면 재측정)")
    ap.add_argument("--settle-deg", type=float, default=None,
                    help="진자 정지 기준: 0.5 s 동안 진폭 (최대−최소)/2 ≤ 값 [°] (기본: 최대−최소 ≤ 6카운트)")
    args = ap.parse_args()
    if (args.fric_file or args.fresh_measure) and not args.comp:
        ap.error("--fric-file / --fresh-measure 는 --comp 와 함께 씁니다")
    if args.fric_file and args.fresh_measure:
        ap.error("--fric-file 과 --fresh-measure 는 함께 쓰지 않습니다")
    if args.no_brake_limit:
        args.brake_plim = None
    if args.settle_deg is not None and not 0 < args.settle_deg <= 30:
        ap.error("--settle-deg 는 0 < 값 ≤ 30")
    if not 1 <= args.iq_max <= CONFIG["IQ_HARD_MAX"]:
        ap.error(f"--iq-max 는 1..{CONFIG['IQ_HARD_MAX']}")
    if args.brake_plim is not None and not (args.brake_plim > 0 and 0 <= args.brake_zone_deg <= 180):
        ap.error("--brake-plim > 0, 0 <= --brake-zone-deg <= 180")
    zone_rad = math.radians(args.brake_zone_deg)
    if args.brake_plim is not None:
        print(f"제동 전력 제한: |φ| > {args.brake_zone_deg:.0f}° 에서 제동 전력 ≤ {args.brake_plim:.1f} W")
    else:
        print("제동 전력 제한 없음 (--no-brake-limit)")
    CONFIG["IQ_MAX"] = args.iq_max
    args.log = args.log or session.log_path("run_policy_dry" if args.dry_run else "run_policy")
    if args.run and CONFIG["alpha_sign"] is None:
        ap.error("alpha_sign 미확정: auto_sign_test.py 결과로 CONFIG 를 먼저 채우세요")
    if args.delay_test:
        motor = Motor(CONFIG)
        session.preflight(motor.bus, None, "run_policy --delay-test")
        ts = []
        for _ in range(100):
            t = time.time()
            st = motor.send_torque(0)
            if st is not None:
                ts.append((time.time() - t) * 1000.0)
            time.sleep(0.02)
        if ts:
            print(f"왕복 지연 ms: 평균 {np.mean(ts):.2f}, 최대 {np.max(ts):.2f}, 응답 {len(ts)}/100")
        else:
            print("응답 없음: CAN 연결 확인")
        motor.shutdown()
        return
    if not (args.dry_run or args.run):
        ap.error("--dry-run, --run, --delay-test 중 하나를 고르세요")

    cfg = CONFIG
    actor = ActorNP(args.policy)
    pend = Pendulum(cfg)
    motor = None if args.dry_run else Motor(cfg)
    if motor:
        session.preflight(motor.bus, pend.bus, "run_policy --run")   # 실패하면 모터 명령 없이 종료

    theta_start = None
    t0 = time.time()
    next_t = t0
    last_ok = t0
    rows = []
    frows = []
    fric = None
    fric_info = {}
    t_main = time.time()
    s_in = 1.0
    state = None                       # 직전 0xA1 응답 (온도, iq, 속도, 각도)
    try:
        if motor and args.run:         # 초기화도 try 안: 실패해도 finally 에서 정지·잠금
            motor.send_brake_release()     # 0x77: 브레이크 해제
            print(f"브레이크 해제 확인 {motor.wait_brake_released():.2f} s")
            if args.comp:
                fric = None
                st0 = motor.send_torque(0)
                temp_now = st0["temp"] if st0 is not None else None
                ffile = args.fric_file or os.path.join(kitparams.LOGS, "kit_params_latest.json")
                if args.fresh_measure:
                    why = "--fresh-measure (무조건 재측정)"
                elif not os.path.exists(ffile):
                    why = f"파일 없음 ({os.path.relpath(ffile)})"
                else:
                    pfile, why = kitparams.reuse_check(ffile, temp_now)
                    if pfile is not None:
                        br = pfile["bridge"]
                        fric = dict(Fc_pos=float(br["Fc_pos"]), Fc_neg=float(br["Fc_neg"]), viscous=float(br["viscous"]),
                                    resid_rms=br.get("resid_rms"), points=[], seconds=0.0)
                        fric_info.update(source="file", file=os.path.relpath(ffile), reason=why, temp_now=temp_now)
                        print(f"마찰값: 파일 재사용, 펄스 생략 — {why} ({os.path.relpath(ffile)})")
                        print(f"파일 값(bridge): Fc+ {fric['Fc_pos']:.3f}, Fc− {fric['Fc_neg']:.3f} N·m, 점성 {fric['viscous']:.4f} N·m·s/rad")
                if fric is None:
                    fric_info.update(source="measured", file=os.path.relpath(ffile), reason=why, temp_now=temp_now)
                    print(f"마찰값: 재측정 — 이유: {why}")
                    print(f"마찰 재측정 시작 (iq {[x for x in cfg['fric_levels'] if x <= args.iq_max]} 양방향, 각 {cfg['fric_pulse_s']} s)")
                    fric = measure_friction(motor, pend, cfg, args.iq_max, frows)
                    try:                       # 재측정 결과를 fric_latest.json 에 (kit_params 형식, replay 없음)
                        temps = [p["temp"] for p in fric["points"]]
                        kp = kitparams.make(dict(Fc_pos=fric["Fc_pos"], Fc_neg=fric["Fc_neg"], viscous=fric["viscous"],
                                                 resid_rms=fric["resid_rms"]), None,
                                            int(round(sum(temps) / len(temps))), os.path.splitext(args.log)[0] + "_fric.csv",
                                            "run_policy.py --comp")
                        kitparams.save(kp, os.path.join(kitparams.LOGS, "fric_latest.json"))
                    except Exception as e:
                        print("fric_latest.json 저장 실패:", e)
                s_in = (cfg["comp_J"] + cfg["J_body"]) / cfg["J_train_total"]
                print(f"보상 (c): 관성 배율 {s_in:.3f}, 쿨롱 보상 +{fric['Fc_pos'] - cfg['train_fc']:.3f}/−{fric['Fc_neg'] - cfg['train_fc']:.3f} N·m, "
                      f"점성 보상 {fric['viscous'] - cfg['train_b']:.4f} N·m·s/rad")
                if args.settle_deg is not None:
                    print(f"진자 정지 기준: 0.5 s 진폭 ≤ {args.settle_deg:g}° (최대−최소 ≤ {2 * args.settle_deg * 4096 / 360:.1f}카운트)")
                print(f"진자 정지 대기 {wait_pendulum_still(pend, cfg, settle_deg=args.settle_deg):.1f} s")
                pend.prev_a = None
            state = motor.send_torque(0)   # 토크 0 으로 첫 상태 읽기
            if state is None:
                raise RuntimeError("초기 상태 응답 없음: CAN/브레이크 확인")
            theta_start = motor.read_angle92()
            if theta_start is None:
                raise RuntimeError("0x92 초기 각도 응답 없음")
            state["a92"] = theta_start
            last_ok = time.time()
            next_t = time.time()
            t0 = next_t
            fric_info["t_to_policy_s"] = round(t0 - t_main, 2)
            print(f"시작~정책 시작 {t0 - t_main:.1f} s")
        while time.time() - t0 < args.seconds:
            now = time.time()
            if now < next_t:
                time.sleep(next_t - now)
                now = time.time()
            next_t += cfg["dt"]

            a92_now = state.get("a92") if state else None     # 영점 식용 0x92 각도 (θ_sim 아님)
            alpha, alpha_dot = pend.read_alpha(now, a92_now)

            if state is not None and theta_start is not None:
                theta = math.radians(state["a92"] - theta_start)   # 시뮬 +θ = +0x92
                theta_dot = math.radians(state["speed_dps"])       # rad/s
            else:
                theta, theta_dot = 0.0, 0.0

            if abs(alpha_dot) > cfg["pend_speed_limit"]:
                raise RuntimeError(f"진자 속도 한계 초과: {alpha_dot:.2f} rad/s")
            if state is not None and abs(state["speed_dps"]) > cfg["arm_speed_limit_dps"]:
                raise RuntimeError(f"팔 속도 한계 초과: {state['speed_dps']} dps")

            obs = np.array([math.cos(theta), math.sin(theta), math.cos(alpha), math.sin(alpha),
                            theta_dot / 20.0, alpha_dot / 40.0])
            u = actor(obs)
            tau_sim = speed_torque_limit(u * args.tau, theta_dot, args.tau, cfg["w_no_load"])
            tau_real = tau_sim                        # 부호 규약: τ_sim = +iq 방향
            if fric is not None:                      # 브리지 보상 (c): 속도-토크 제한 뒤에 더함
                fc = fric["Fc_pos"] if theta_dot > 0 else fric["Fc_neg"]
                tau_real = (s_in * tau_sim + (fc - cfg["train_fc"]) * math.tanh(theta_dot / cfg["comp_eps"])
                            + (fric["viscous"] - cfg["train_b"]) * theta_dot)
            tau_unlim = tau_real
            if args.brake_plim is not None:           # 제동 제한: iq 상한으로 자른 뒤 적용
                lim = cfg["IQ_MAX"] * 0.01 * cfg["KT"]
                tau_real = brake_limit(max(-lim, min(lim, tau_real)), theta_dot, wrap(alpha - math.pi),
                                       args.brake_plim, zone_rad)
            iq = torque_to_iq(tau_real, cfg)
            tau_q = iq * 0.01 * cfg["KT"]
            brake_w = abs(tau_q * theta_dot) if tau_q * theta_dot < 0 else 0.0

            rows.append([round(now - t0, 3), theta, theta_dot, alpha, alpha_dot, u, iq,
                         state["angle_deg"] if state else "", state.get("a92", "") if state else "",
                         state["speed_dps"] if state else "", pend.last_raw, round(pend.last_zero, 1),
                         state["iq"] if state else "", state["temp"] if state else "", round(tau_real, 4),
                         round(tau_unlim, 4), round(brake_w, 3), int(abs(tau_real - tau_unlim) > 1e-9),
                         state.get("st1", "") if state else ""])

            if motor and args.run:
                new = motor.send_torque(iq)   # 명령과 상태 응답이 한 번에 옴
                if new is None:
                    if time.time() - last_ok > cfg["watchdog"]:
                        raise RuntimeError("워치독: 모터 응답 없음")
                else:
                    a92 = motor.read_angle92()
                    new["a92"] = a92 if a92 is not None else state.get("a92")
                    if args.log_voltage:      # 0x9A 상태 1, 응답 8바이트 그대로 (없으면 빈칸)
                        st1 = motor.xfer(bytes([0x9A, 0, 0, 0, 0, 0, 0, 0]), timeout=0.005)
                        new["st1"] = st1.hex() if st1 is not None else ""
                    state = new
                    last_ok = time.time()
    finally:
        if motor and args.run:
            graceful_stop(motor, cfg)
        if motor:
            try:
                print("마지막 0x92 각도 저장:", session.record_end_angle(motor.bus))
            except Exception as e:
                print("마지막 각도 저장 실패:", e)
            motor.shutdown()
        with open(args.log, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["t", "theta", "theta_dot", "alpha", "alpha_dot", "u", "iq", "angle_deg", "a92_deg", "speed_dps",
                        "pend_raw", "pend_zero_raw", "iq_reply_prev", "temp_C", "tau_cmd",
                        "tau_unlim", "brake_w", "brake_limited", "st1_hex"])
            w.writerows(rows)
        if frows or fric is not None:
            base = os.path.splitext(args.log)[0]
            if frows:
                with open(base + "_fric.csv", "w", newline="") as fh:
                    w = csv.writer(fh)
                    w.writerow(["t", "iq_cmd", "iq_reply", "speed_dps", "temp_C", "pend_raw"])
                    w.writerows(frows)
            if fric is not None:
                import json
                json.dump(dict(fric, s_inertia=s_in, comp_J=cfg["comp_J"], iq_max=args.iq_max, tau=args.tau,
                               brake_plim=args.brake_plim, brake_zone_deg=args.brake_zone_deg if args.brake_plim else None,
                               log_voltage=args.log_voltage, settle_deg=args.settle_deg, fric_info=fric_info),
                          open(base + "_fric.json", "w"), ensure_ascii=False, indent=1)
            print("마찰 기록:", (base + "_fric.csv, ") if frows else "", base + "_fric.json")
        if SETTLE_LOG:
            base = os.path.splitext(args.log)[0]
            with open(base + "_settle.csv", "w", newline="") as fh:
                w = csv.writer(fh)
                w.writerow(["t", "pend_raw"])
                w.writerows(SETTLE_LOG)
        print(f"로그 {len(rows)}행 저장: {args.log}")
        if frows and fric is not None and fric_info.get("source") == "measured" and getattr(measure_friction, "last", None):
            try:                               # 정책이 끝난 뒤(모터 정지·잠금 후) MuJoCo 용 값까지 계산해 kit_params 저장
                import kit_identify
                base = os.path.splitext(args.log)[0]
                stamp = os.path.basename(base).replace("run_policy_", "")
                print("재측정 기록으로 MuJoCo 용 값 계산(quick_id) ...", flush=True)
                kit_identify.analyze(base + "_fric.csv", frows, measure_friction.last, [], stamp, made_by="run_policy.py --comp")
            except Exception as e:
                print("kit_params 저장 실패:", e)


if __name__ == "__main__":
    main()
