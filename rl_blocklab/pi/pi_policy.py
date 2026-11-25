"""
pi_policy.py — 라즈베리파이에서 학습된 정책 실행하기
===================================================
RL 블록 실험실에서 '라즈베리파이로' 내보낸 폴더를 그대로 라즈베리파이에 복사해서 쓴다.
  policy.npz        신경망 가중치 (numpy)
  policy_meta.json  관측 순서, 제어 주기, 최대 토크, 확인용 테스트 값
  pi_policy.py      이 파일

필요한 것: Python 3 + numpy 만 (PyTorch, MuJoCo 필요 없음)
  sudo apt install python3-numpy      # 또는 pip install numpy
  (실제 기계를 돌릴 때 시리얼 통신을 쓰면) pip install pyserial

실행
  python3 pi_policy.py --test           # 1) 시뮬레이션에서 낸 답과 똑같이 계산되는지 확인 (기계 없이)
  python3 pi_policy.py --bench          # 2) 한 번 계산하는 데 몇 ms 걸리는지 (제어 주기보다 훨씬 짧아야 함)
  python3 pi_policy.py --run --port /dev/ttyACM0   # 3) 실제 진자 제어

중요: 시뮬레이션과 똑같은 약속을 지켜야 정책이 제대로 동작한다.
  - θ(진자각)는 아래로 매달렸을 때 0, 위로 섰을 때 ±π  (rad)
  - φ(팔각)는 시작 위치가 0, 반시계(+)/시계(-) 방향이 MuJoCo 모델과 같아야 함
  - 정책 출력 a(-1~+1) × 최대 토크 = 모터 토크.  모터 방향(+/-)도 시뮬레이션과 같아야 함
  - 제어 주기 = policy_meta.json 의 ctrl_dt
"""
import argparse
import json
import math
import os
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))


# ============================================================ 정책 (신경망 계산)
class Policy:
    def __init__(self, folder=HERE):
        with open(os.path.join(folder, "policy_meta.json"), encoding="utf-8") as f:
            self.meta = json.load(f)
        z = np.load(os.path.join(folder, "policy.npz"))
        n = len(self.meta["layers"])
        self.Ws = [z[f"W{i}"] for i in range(n)]
        self.bs = [z[f"b{i}"] for i in range(n)]
        self.act = np.tanh if self.meta["activation"] == "tanh" else (lambda x: np.maximum(x, 0))

    def __call__(self, obs):
        """obs = [cos θ, sin θ, φ, φ̇, θ̇]  →  a (-1 ~ +1)"""
        x = np.asarray(obs, dtype=np.float32)
        for i, (W, b) in enumerate(zip(self.Ws, self.bs)):
            x = W @ x + b
            if i < len(self.Ws) - 1:
                x = self.act(x)
        return float(np.clip(x[0], -1.0, 1.0))


def make_obs(theta, phi, theta_dot, phi_dot):
    return [math.cos(theta), math.sin(theta), phi, phi_dot, theta_dot]


# ============================================================ 하드웨어 연결 (우리 기계에 맞게 고칠 부분)
class SerialMotorBridge:
    """
    예시: 모터 드라이버(FOC) MCU와 시리얼로 주고받는 방식.
      라즈베리파이 → MCU : "T<토크 N·m>\\n"            예) T0.0123
      MCU → 라즈베리파이 : "<팔각 rad>,<진자각 rad>\\n"  예) 0.0123,3.1002
    MCU 펌웨어의 실제 형식에 맞게 read_angles()/send_torque() 를 고쳐 쓰면 된다.
    """

    def __init__(self, port, baud=115200):
        import serial                      # pip install pyserial
        self.ser = serial.Serial(port, baud, timeout=0.05)
        self.ser.reset_input_buffer()

    def read_angles(self):
        line = self.ser.readline().decode(errors="ignore").strip()
        arm, pend = (float(v) for v in line.split(","))
        return arm, pend

    def send_torque(self, tau):
        self.ser.write(f"T{tau:.5f}\n".encode())

    def close(self):
        self.send_torque(0.0)
        self.ser.close()


# ============================================================ 실행 모드
def selftest(pol):
    m = pol.meta
    diffs = [abs(pol(o) - a) for o, a in zip(m["test_obs"], m["test_act"])]
    ok = max(diffs) < 1e-4
    print(f"정책: {m['name']}  (신경망 {m['layers']}, 활성화 {m['activation']})")
    print(f"테스트 {len(diffs)}개, 시뮬레이션과의 최대 차이 = {max(diffs):.2e}  →  {'통과 ✅' if ok else '실패 ❌'}")
    print(f"제어 주기 {m['ctrl_dt'] * 1000:.1f} ms, 최대 토크 {m['max_torque_nm']} N·m")
    return ok


def bench(pol, n=2000):
    obs = pol.meta["test_obs"][0]
    t0 = time.perf_counter()
    for _ in range(n):
        pol(obs)
    ms = (time.perf_counter() - t0) / n * 1000
    print(f"정책 1회 계산: {ms:.3f} ms  (제어 주기 {pol.meta['ctrl_dt'] * 1000:.1f} ms)")


def run(pol, port, arm_limit, seconds):
    dt = pol.meta["ctrl_dt"]
    max_tau = pol.meta["max_torque_nm"]
    hw = SerialMotorBridge(port)
    print("제어 시작 (Ctrl+C 로 정지). 진자를 아래로 가만히 둔 상태에서 시작하세요.")
    arm0, pend0 = hw.read_angles()                     # 시작 자세를 0으로 (진자 아래로 매달림)
    prev = None
    vel = np.zeros(2)                                  # [φ̇, θ̇]  (간단한 저역 필터)
    t_next = time.perf_counter()
    t_end = t_next + seconds if seconds > 0 else float("inf")
    try:
        while time.perf_counter() < t_end:
            arm, pend = hw.read_angles()
            phi, theta = arm - arm0, pend - pend0
            if prev is not None:
                raw = np.array([phi - prev[0], theta - prev[1]]) / dt
                vel = 0.7 * vel + 0.3 * raw
            prev = (phi, theta)
            if abs(phi) > arm_limit:                   # 안전: 팔이 너무 많이 돌면 정지
                print(f"팔 각도 {math.degrees(phi):.0f}° → 안전 정지")
                break
            a = pol(make_obs(theta, phi, vel[1], vel[0]))
            hw.send_torque(a * max_tau)
            t_next += dt
            time.sleep(max(0.0, t_next - time.perf_counter()))
    except KeyboardInterrupt:
        pass
    finally:
        hw.close()
        print("모터 정지")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="학습된 퓨루타 진자 정책 실행")
    ap.add_argument("--test", action="store_true", help="시뮬레이션과 같은 답이 나오는지 확인")
    ap.add_argument("--bench", action="store_true", help="계산 속도 측정")
    ap.add_argument("--run", action="store_true", help="실제 기계 제어")
    ap.add_argument("--port", default="/dev/ttyACM0", help="모터 드라이버 시리얼 포트")
    ap.add_argument("--arm-limit", type=float, default=math.radians(720), help="안전 정지 팔 각도 (rad)")
    ap.add_argument("--seconds", type=float, default=0, help="제어 시간 (0 = Ctrl+C 까지)")
    args = ap.parse_args()
    policy = Policy()
    if args.run:
        if selftest(policy):
            run(policy, args.port, args.arm_limit, args.seconds)
    elif args.bench:
        bench(policy)
    else:
        selftest(policy)
