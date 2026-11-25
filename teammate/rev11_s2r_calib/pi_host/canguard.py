"""can0 상태 점검. 모든 실험 스크립트가 시작할 때와 루프 도중에 부른다.

오늘 확인된 원인: PC(MATLAB/Simulink)에서 SSH로 Pi에 배포한 furuta_pi_*.elf 가 시작할 때마다
`sudo ip link set can0 down` -> `up type can bitrate <모델 설정값, 500000 이었던 적 있음>` 을 실행하고,
그 뒤 자기도 CAN 명령을 보낸다. 그래서
  - full_check(): 링크 UP, ERROR-ACTIVE, bitrate 1000000, 다른 CAN 송신 프로세스 없음
  - fast_check(): operstate 가 up 인지 (루프마다, 매우 가벼움)
  - foreign_frame(msg): 우리 소켓이 받은 0x141 프레임 = 다른 프로세스가 모터에 명령을 보낸 것
    (python-can 은 기본적으로 자기 송신 프레임을 돌려받지 않음)
"""
import json
import subprocess

IFACE = "can0"
BITRATE = 1000000
REQ_ID = 0x141
# 다른 CAN 송신자 후보. candump(수신만)는 허용.
FOREIGN_PATTERNS = [r"\.elf", "furuta_pi_", "cansend", "run_policy.py", "check_hw.py", "auto_sign_test.py"]


class CanGuardError(RuntimeError):
    pass


def _link():
    out = subprocess.run(["ip", "-details", "-json", "link", "show", IFACE],
                         capture_output=True, text=True, timeout=1.0)
    if out.returncode != 0:
        raise CanGuardError(f"{IFACE} 정보 읽기 실패: {out.stderr.strip()}")
    return json.loads(out.stdout)[0]


def foreign_processes(self_pid=None):
    import os
    me = self_pid or os.getpid()
    found = []
    for pat in FOREIGN_PATTERNS:
        r = subprocess.run(["pgrep", "-af", pat], capture_output=True, text=True)
        for line in r.stdout.splitlines():
            pid = int(line.split()[0])
            if pid != me and pid != os.getppid() and "pgrep" not in line and "bash -c" not in line:
                found.append(line.strip())
    return sorted(set(found))


def full_check(check_processes=True):
    """이상하면 CanGuardError. 정상이면 상태 문자열."""
    d = _link()
    flags = d.get("flags", [])
    info = d.get("linkinfo", {}).get("info_data", {})
    state = info.get("state")
    bitrate = info.get("bittiming", {}).get("bitrate")
    problems = []
    if "UP" not in flags or d.get("operstate") not in ("UP", "UNKNOWN"):
        problems.append(f"링크 꺼짐 (flags={flags}, operstate={d.get('operstate')})")
    if state != "ERROR-ACTIVE":
        problems.append(f"CAN 상태 {state}")
    if bitrate != BITRATE:
        problems.append(f"bitrate {bitrate} (1000000 이어야 함). 복구: sudo ip link set can0 down && "
                        f"sudo ip link set can0 up type can bitrate 1000000")
    if check_processes:
        fp = foreign_processes()
        if fp:
            problems.append("다른 CAN 송신 프로세스: " + " | ".join(fp))
    if problems:
        raise CanGuardError("; ".join(problems))
    return f"{IFACE} UP, {state}, {bitrate} bps"


def fast_check():
    try:
        with open(f"/sys/class/net/{IFACE}/operstate") as fh:
            st = fh.read().strip()
    except OSError as e:
        raise CanGuardError(f"{IFACE} operstate 읽기 실패: {e}")
    if st not in ("up", "unknown"):
        raise CanGuardError(f"{IFACE} operstate={st} (도중에 꺼짐)")


def foreign_frame(msg):
    """우리 소켓으로 들어온 0x141 = 다른 프로세스가 보낸 모터 명령."""
    if msg is not None and msg.arbitration_id == REQ_ID:
        raise CanGuardError(f"다른 프로세스의 모터 명령 감지: 0x141 {bytes(msg.data).hex(' ')}")


if __name__ == "__main__":
    try:
        print("정상:", full_check())
    except CanGuardError as e:
        print("이상:", e)
        raise SystemExit(1)
