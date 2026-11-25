"""교구 마찰·관성 값 파일(kit_params_*.json, fric_latest.json) 공통 형식과 재사용 판정.

형식:
{
  "measured_kst": "2026-11-20 15:30:00", "epoch": 1795...,       # 측정 시각
  "temp_C": 40,                                                   # 측정 중 모터 온도(평균, 0xA1 응답 DATA[1])
  "valid": true, "invalid_reasons": [],
  "bridge": {"Fc_pos":…, "Fc_neg":…, "viscous":…, "resid_rms":…},   # 일정속도 최소제곱 (브리지 보상용, measure_friction 과 같음)
  "replay": {"J":…, "Fc_pos":…, "Fc_neg":…, "viscous":…, "speed_rms_dps":…} 또는 null,  # quick_id 재생 맞춤 (MuJoCo 학습용)
  "source": "logs/….csv", "made_by": "kit_identify.py" | "run_policy.py --comp"
}
"""
import os
import json
import time
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
LOGS = os.path.join(os.path.dirname(HERE), "logs")   # 패키지: 최상위 logs/
RANGES = dict(J=(0.015, 0.035), Fc=(0.05, 1.5), b=(0.0, 0.6), speed_rms_dps=(0.0, 40.0))
REUSE_MAX_AGE_S = 30 * 60
REUSE_MAX_DTEMP = 3.0


def kst_now():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M:%S")


def check_ranges(bridge, replay):
    bad = []
    for k in ("Fc_pos", "Fc_neg"):
        lo, hi = RANGES["Fc"]
        if not lo <= bridge[k] <= hi:
            bad.append(f"bridge {k} {bridge[k]:.3f} 범위 밖({lo}~{hi})")
    lo, hi = RANGES["b"]
    if not lo <= bridge["viscous"] <= hi:
        bad.append(f"bridge b {bridge['viscous']:.4f} 범위 밖({lo}~{hi})")
    if replay is not None:
        lo, hi = RANGES["J"]
        if not lo <= replay["J"] <= hi:
            bad.append(f"replay J {replay['J']:.4f} 범위 밖({lo}~{hi})")
        for k in ("Fc_pos", "Fc_neg"):
            lo, hi = RANGES["Fc"]
            if not lo <= replay[k] <= hi:
                bad.append(f"replay {k} {replay[k]:.3f} 범위 밖({lo}~{hi})")
        lo, hi = RANGES["b"]
        if not lo <= replay["viscous"] <= hi:
            bad.append(f"replay b {replay['viscous']:.4f} 범위 밖({lo}~{hi})")
        if not replay["speed_rms_dps"] < RANGES["speed_rms_dps"][1]:
            bad.append(f"replay 속도 RMS {replay['speed_rms_dps']:.1f} dps ≥ 40")
    return bad


def make(bridge, replay, temp_C, source, made_by, extra_bad=()):
    bad = list(extra_bad) + check_ranges(bridge, replay)
    return dict(measured_kst=kst_now(), epoch=time.time(), temp_C=temp_C, valid=not bad, invalid_reasons=bad,
                bridge=bridge, replay=replay, source=os.path.relpath(source, os.path.dirname(HERE)), made_by=made_by)


def save(params, *paths):
    for p in paths:
        json.dump(params, open(p, "w"), ensure_ascii=False, indent=1)


def reuse_check(path, temp_now):
    """(params 또는 None, 이유 문자열). None 이면 재측정해야 함."""
    try:
        p = json.load(open(path))
    except Exception as e:
        return None, f"파일 읽기 실패({e})"
    try:
        if not p.get("valid", False):
            return None, f"invalid 표시({'; '.join(p.get('invalid_reasons', []))})"
        age = time.time() - float(p["epoch"])
        if age > REUSE_MAX_AGE_S:
            return None, f"측정 뒤 {age / 60:.0f}분 지남(30분 초과, 측정 {p.get('measured_kst')})"
        if age < 0:
            return None, "측정 시각이 미래(시계 확인)"
        if temp_now is None:
            return None, "현재 모터 온도 읽기 실패"
        dT = temp_now - float(p["temp_C"])
        if abs(dT) > REUSE_MAX_DTEMP:
            return None, f"모터 온도 차 {dT:+.0f}°C(측정 {p['temp_C']}°C, 지금 {temp_now}°C, 3°C 초과)"
        br = p["bridge"]
        for k in ("Fc_pos", "Fc_neg", "viscous"):
            float(br[k])
    except (KeyError, TypeError, ValueError) as e:
        return None, f"파일 형식 오류({e})"
    return p, f"재사용: 측정 {p['measured_kst']} ({age / 60:.1f}분 전), 온도 {p['temp_C']}→{temp_now}°C"
