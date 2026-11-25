"""Build RESULTS.md tables from results_matlab_policies.json, results_teammate.json, bench_*.json."""
import json, os, glob
H = os.path.dirname(os.path.abspath(__file__))
R = json.load(open(os.path.join(H, "results_matlab_policies.json")))
CONDS = ["nom10", "d20", "fric075", "fric125", "inert085", "inert115", "hw1123", "d20_fric125"]
HW = {"run9_rev11_regen/ck_0380": "통과 (11/20)", "run10_rev11_bias/ck_0250": "20 s 유지 2/3, 엄격 0/3",
      "run12_rev11_hold_lo/ck_0300": "엄격 1/3", "run13_rev11_delay/ck_0300": "미시험",
      "sac19_rev11_regen/ck_0100": "실패", "sac22_rev11_stic2x/ck_0150": "엄격 3/3",
      "sac22_rev11_stic2x/ck_0400": "실패 0/3", "sac24_rev11_armrate2/ck_0100": "엄격 3/3",
      "sac24_rev11_armrate2/ck_0200": "엄격 3/3", "sac25_v3_opt/ck_0150": "엄격 2/3 (Pi 정지 1회)",
      "sac25_v3_opt/ck_0200": "미시험"}
L = []
L.append("## 1. 포팅 검증: Python 해석 모델 vs MATLAB sp_eval2\n")
tot = sum(1 for r in R); same = sum(r["py_analytic"] == r["matlab"] for r in R)
vec = sum(sum(a == b for a, b in zip(r["py_analytic_vec"], r["matlab_vec"])) for r in R)
L.append(f"정책 11개 × 조건 8개 = {tot}칸 중 통과 개수 일치 {same}/{tot}, 시작점 단위 일치 {vec}/{tot*16}.\n")
for plant, title in [("mj_ident", "2. MuJoCo (rev11 CAD + 식별 마찰·관성, 결합항 gam ×0.8 = MATLAB 식별 플랜트와 같은 계수)"),
                     ("mj_cad", "3. MuJoCo (rev11 CAD 결합항 그대로, 마찰·관성은 식별값)")]:
    L.append(f"\n## {title}\n")
    L.append("각 칸: MATLAB → MuJoCo (16개 고정 시작 중 엄격 기준 통과 수)\n")
    L.append("| 정책 | 실물 | " + " | ".join(CONDS) + " | 합계 |")
    L.append("|---|---|" + "---|" * (len(CONDS) + 1))
    for ck in dict.fromkeys(r["ck"] for r in R):
        rs = {r["cond"]: r for r in R if r["ck"] == ck}
        cells = []; sm = sp = 0
        for cn in CONDS:
            r = rs[cn]; sm += r["matlab"]; sp += r[plant]
            mark = "" if abs(r[plant] - r["matlab"]) <= 1 else (" ▲" if r[plant] > r["matlab"] else " ▼")
            cells.append(f"{r['matlab']}→{r[plant]}{mark}")
        L.append(f"| {ck.replace('_rev11','').replace('/ck_',' ck')} | {HW.get(ck,'')} | " + " | ".join(cells) + f" | {sm}→{sp} /128 |")
T = os.path.join(H, "results_teammate.json")
if os.path.exists(T):
    TM = json.load(open(T))
    L.append("\n## 4. 팀원 SAC (sac_rev11, 50 Hz, 브리지 보상 (c) + 1.2 A + 제동 5 W)\n")
    L.append("| 조건 | 지연 | MuJoCo CAD | MuJoCo 식별 | Python 해석 | 보상 없음 (CAD/식별/해석) |")
    L.append("|---|---|---|---|---|---|")
    for r in TM:
        L.append(f"| {r['cond']} | {r['delay_ms']:.0f} ms | {r['mj_cad']}/16 | {r['mj_ident']}/16 | {r['py_analytic']}/16 | "
                 f"{r['mj_cad_nocomp']}/{r['mj_ident_nocomp']}/{r['py_analytic_nocomp']} |")
B = sorted(glob.glob(os.path.join(H, "bench_*.json")))
if B:
    L.append("\n## 5. 학습 시간 (같은 PC)\n")
    L.append("| 알고리즘 | 구현 | 반복 | 롤아웃 s | 업데이트 s | 합계 s |")
    L.append("|---|---|---|---|---|---|")
    L.append("| SAC v3 | MATLAB (bench_sac_opt) | 100 | 10.2 | 1498.5 | 1534 (평가 25 s 포함) |")
    L.append("| PPO | MATLAB (bench_ppo_base_s1) | 150 | – | – | 273.1 |")
    for f in B:
        b = json.load(open(f))
        L.append(f"| {b['which'].upper()} | PyTorch {b['torch']} CPU, {b['threads']} threads | {b['iters']} | {b['roll_s']:.1f} | {b['upd_s']:.1f} | {b['total_s']:.1f} |")
open(os.path.join(H, "RESULTS_tables.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
print("\n".join(L))
