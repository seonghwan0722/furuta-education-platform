"""교구(실기) 팔 마찰·관성 측정: run_policy 의 마찰 재측정 펄스를 그대로 쓰고, 두 가지 값을 따로 남긴다.

  python3 pi_host/kit_identify.py --dry-run     # 모터 명령 없음: 할 일 출력 + 기존 기록으로 분석 단계 시험
  python3 pi_host/kit_identify.py --run         # 실제 측정 (사용자 확인 후)

순서(--run): 세션 점검(session.preflight) → 0x77 브레이크 해제·확인 → measure_friction 과 같은 펄스
  (±0.6/0.8/1.0 A, 각 0.8 s, 펄스 뒤 팔 정지 대기) → graceful_stop(iq 0 → 0x81 → 0x78 → 속도 확인 뒤 0x80) → 각도 저장.
기록: logs/kit_id_YYYYmmdd_HHMMSS.csv (run_policy _fric.csv 와 같은 열).
결과 두 가지:
  (1) replay: sim/quick_id.py 재생 맞춤 J, Fc+, Fc−, b, 속도 RMS (MuJoCo 학습용, .venv 파이썬으로 실행)
  (2) bridge: measure_friction 이 돌려준 일정속도 최소제곱 Fc+, Fc−, b, 잔차 그대로 (브리지 보상용)
→ logs/kit_params_YYYYmmdd_HHMMSS.json, logs/kit_params_latest.json (kitparams.py 형식).
정상 범위(kitparams.RANGES): J 0.015~0.035, Fc 0.05~1.5, b 0~0.6, 속도 RMS < 40 dps. 벗어나도 저장하고 valid=false.
"""
import os
import sys
import csv
import json
import math
import time
import argparse
import subprocess

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import run_policy as rp  # noqa: E402
import session  # noqa: E402
import kitparams  # noqa: E402

VENV_PY = os.path.join(ROOT, ".venv", "bin", "python")
QUICK_ID = os.path.join(ROOT, "sim", "quick_id.py")
COLS = ["t", "iq_cmd", "iq_reply", "speed_dps", "temp_C", "pend_raw"]


def run_replay(csv_path):
    """sim/quick_id.py 를 .venv 로 실행. 실패하면 (None, 이유)."""
    try:
        out = subprocess.run(["taskset", "-c", "0-2", VENV_PY, QUICK_ID, csv_path], capture_output=True, text=True, timeout=600)
        line = [x for x in out.stdout.splitlines() if x.startswith("{")]
        if out.returncode != 0 or not line:
            return None, f"quick_id 실패(rc {out.returncode}): {out.stderr.strip()[-200:]}"
        r = json.loads(line[-1])
        return dict(J=r["J"], Fc_pos=r["Fc_pos"], Fc_neg=r["Fc_neg"], viscous=r["viscous"],
                    speed_rms_dps=r["speed_rms_dps"]), None
    except Exception as e:
        return None, f"quick_id 실행 오류({e})"


def analyze(csv_path, frows, mf, extra_bad, stamp, save=True, made_by="kit_identify.py"):
    """mf: measure_friction 결과(dict). bridge 값은 그대로 씀."""
    bridge = dict(Fc_pos=mf["Fc_pos"], Fc_neg=mf["Fc_neg"], viscous=mf["viscous"], resid_rms=mf["resid_rms"])
    pts = mf.get("points", [])
    bad = list(extra_bad)
    replay, why = run_replay(csv_path)
    if replay is None:
        bad.append(why)
    temps = [float(r[4]) for r in frows]
    kp = kitparams.make(bridge, replay, int(round(sum(temps) / len(temps))), csv_path, made_by, bad)
    kp["temp_range_C"] = [min(temps), max(temps)]
    kp["pulses"] = pts
    print(f"(2) 브리지 보상용 일정속도 최소제곱: Fc+ {bridge['Fc_pos']:.3f}, Fc− {bridge['Fc_neg']:.3f} N·m, "
          f"점성 {bridge['viscous']:.4f} N·m·s/rad, 잔차 {bridge['resid_rms']:.3f} N·m")
    if replay:
        print(f"(1) MuJoCo 학습용 재생 맞춤: J {replay['J']:.4f} kg·m², Fc+ {replay['Fc_pos']:.3f}, Fc− {replay['Fc_neg']:.3f} N·m, "
              f"점성 {replay['viscous']:.4f}, 속도 RMS {replay['speed_rms_dps']:.1f} dps")
    print(f"모터 온도 {kp['temp_range_C'][0]:.0f}~{kp['temp_range_C'][1]:.0f}°C, 측정 {kp['measured_kst']} KST, "
          f"{'valid' if kp['valid'] else 'INVALID: ' + '; '.join(kp['invalid_reasons'])}")
    if save:
        p1 = os.path.join(kitparams.LOGS, f"kit_params_{stamp}.json")
        p2 = os.path.join(kitparams.LOGS, "kit_params_latest.json")
        kitparams.save(kp, p1, p2)
        print("저장:", p1, "/", p2)
    return kp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--iq-max", type=int, default=100, help="펄스 최대 iq (0.01 A), 기본 100 = ±0.6/0.8/1.0 A")
    ap.add_argument("--test-csv", default=None,
                    help="--dry-run 에서 분석 단계 시험에 쓸 기존 기록 (기본: logs/ 의 가장 최근 kit_id_*.csv)")
    a = ap.parse_args()
    cfg = rp.CONFIG
    levels = [x for x in cfg["fric_levels"] if x <= a.iq_max]
    if not levels or a.iq_max > 120:
        ap.error("--iq-max 는 60~120")
    if a.dry_run == a.run:
        ap.error("--dry-run 또는 --run 중 하나")
    plan = (f"세션 점검 → 0x77 브레이크 해제·확인 → 펄스 iq {['±%d' % x for x in levels]} (각 {cfg['fric_pulse_s']} s, 사이마다 iq 0 으로 팔 정지 대기, "
            f"팔 속도 한계 {cfg['arm_speed_limit_dps']} dps) → iq 0 → 0x81 → 0x78 → 0x92 각도 저장. 약 {len(levels) * 2 * 1.3 + 4:.0f} s")
    if a.dry_run:
        if a.test_csv is None:
            import glob
            c = sorted(glob.glob(os.path.join(kitparams.LOGS, "kit_id_*.csv")))
            a.test_csv = c[-1] if c else os.path.join(kitparams.LOGS, "run_policy_20261118_192014_fric.csv")
        print("[dry-run] 모터 명령을 보내지 않습니다.")
        print("[dry-run] --run 이면:", plan)
        print("[dry-run] 기록 열:", COLS)
        print("[dry-run] 분석 단계 시험(저장 안 함):", a.test_csv)
        frows = [[r.get(c, "") for c in COLS[:5]] + [r.get("pend_raw", "")] for r in csv.DictReader(open(a.test_csv))]
        base = os.path.splitext(a.test_csv)[0]
        if os.path.basename(base).startswith("kit_id_"):                  # 그 측정 때 measure_friction 결과(bridge)
            d, n = os.path.split(base)
            kp_old = json.load(open(os.path.join(d, n.replace("kit_id_", "kit_params_", 1) + ".json")))
            mf = dict(kp_old["bridge"], points=kp_old.get("pulses", []))
        else:
            mf = json.load(open(base + ".json"))
        analyze(a.test_csv, frows, mf, [], "dry", save=False)
        return
    stamp = time.strftime("%Y%m%d_%H%M%S")
    csv_path = os.path.join(kitparams.LOGS, f"kit_id_{stamp}.csv")
    motor = rp.Motor(cfg)
    pend = rp.Pendulum(cfg)
    session.preflight(motor.bus, pend.bus, "kit_identify --run")     # 실패하면 모터 명령 없이 종료
    frows, err = [], []
    print(plan)
    try:
        motor.send_brake_release()
        print(f"브레이크 해제 확인 {motor.wait_brake_released():.2f} s")
        rp.measure_friction.last = None
        try:
            rp.measure_friction(motor, pend, cfg, a.iq_max, frows)
        except RuntimeError as e:          # 결과 비정상(범위·일정속도) — 기록은 남기고 invalid 표시
            if not frows or "응답 없음" in str(e) or "한계" in str(e):
                raise
            err.append(str(e))
    finally:
        rp.graceful_stop(motor, cfg)
        try:
            print("마지막 0x92 각도 저장:", session.record_end_angle(motor.bus))
        except Exception as e:
            print("마지막 각도 저장 실패:", e)
        motor.shutdown()
        if frows:
            with open(csv_path, "w", newline="") as fh:
                w = csv.writer(fh)
                w.writerow(COLS)
                w.writerows(frows)
            print("기록:", csv_path)
    mf = getattr(rp.measure_friction, "last", None)
    if mf is None:
        print("measure_friction 결과 없음 -> 분석 안 함")
        return
    analyze(csv_path, frows, mf, err, stamp)


if __name__ == "__main__":
    main()
