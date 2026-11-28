"""Build tables + figures for rev22 SAC/PPO/CEM selection report. Reads only raw result json files."""
import json, os, math, sys
import numpy as np, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
fm.fontManager.addfont('/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc')
plt.rcParams.update({'font.family': 'WenQuanYi Zen Hei', 'axes.unicode_minus': False, 'font.size': 9})

OUT = sys.argv[1]; os.makedirs(OUT + '/figures', exist_ok=True)
RL = os.environ.get('RLDIR','../../../d2/rev22_rl_deliverables/results/'); CEMR = '/mnt/project-files/rev22_control/cem/results/'
ORDER = ['SAC_Py', 'SAC_ML', 'PPO_ML', 'PPO_Py', 'PPO_Py_own', 'CEM']
LAB = {'SAC_Py': 'SAC Python ck100', 'SAC_ML': 'SAC MATLAB ck050', 'PPO_ML': 'PPO MATLAB ck080\n(SAC출발+γDR)',
       'PPO_Py': 'PPO Python ck120\n(SAC출발+γDR)', 'PPO_Py_own': 'PPO Python s2 ck200\n(PPO 단독 계보)', 'CEM': 'CEM\n(Python=MATLAB)'}
LAB1 = {k: v.replace('\n', ' ') for k, v in LAB.items()}
SH = {'SAC_Py': 'SAC Py ck100', 'SAC_ML': 'SAC ML ck050', 'PPO_ML': 'PPO ML ck080', 'PPO_Py': 'PPO Py ck120', 'PPO_Py_own': 'PPO Py 단독', 'CEM': 'CEM'}
COL = {'SAC_Py': '#1f77b4', 'SAC_ML': '#6baed6', 'PPO_ML': '#d62728', 'PPO_Py': '#fc9272', 'PPO_Py_own': '#a50f15', 'CEM': '#2ca02c'}
SRC = {'SAC_Py': ('eval_py_sac.json', 'py_sac_ck100'), 'SAC_ML': ('eval_ml.json', 'ml_sac_ck050'), 'PPO_ML': ('eval_ml_ppo2.json', 'ml_ppo_sacinitg_ck080'),
       'PPO_Py': ('eval_py_ppo3.json', 'py_ppo_sacinitg_ck120'), 'PPO_Py_own': ('eval_py_ppo2.json', 'py_ppo_rwdef_s2_ck200')}
GK = {'SAC_Py': 'py_sac_ck100', 'SAC_ML': 'ml_sac_ck050', 'PPO_ML': 'ml_ppo_sacinitg_ck080', 'PPO_Py': 'py_ppo_sacinitg_ck120', 'PPO_Py_own': 'py_ppo_rwdef_s2_ck200'}
EX = {k: json.load(open(RL + f))[n] for k, (f, n) in SRC.items()}
EX['CEM'] = json.load(open(CEMR + 'vx_cem_nom_by_ident09.json'))
GAM = json.load(open(RL + 'gam_sweep.json'))
ST = {k: json.load(open(f'stress_{k}.json')) for k in ORDER}
from stress import SW
NA = None

# ---------------- existing (in-DR) conditions
EXC = [('d10', '공칭 10 ms', 123), ('d15', '공칭 15 ms', 123), ('d20', '공칭 20 ms', 123), ('gam08', 'γ×0.8', 43), ('gam12', 'γ×1.2', 43),
       ('coul05', '쿨롱×0.5', 43), ('coul125', '쿨롱×1.25', 43), ('alpha085', 'α×0.85', 43), ('alpha115', 'α×1.15', 43), ('swap', '마찰 교환(rev11 식별)', 43),
       ('hwlike', '실물형 10 ms', 43), ('hwlike_d20', '실물형 20 ms', 43), ('mj_d10', 'MuJoCo 10 ms', 16), ('mj_d20', 'MuJoCo 20 ms', 16)]
def exv(k, c):
    r = EX[k].get(c); return (r['passed'], r['n']) if r else NA
GAMS = [0.7, 0.8, 0.9, 1.0, 1.1, 1.2]
def gamv(k, g, d='d20'):
    if k != 'CEM': return (GAM[GK[k]][f'{g}_{d}'], 43)
    m = {0.8: 'gam08' + ('_d20' if d == 'd20' else ''), 1.2: 'gam12' + ('_d20' if d == 'd20' else ''), 1.0: d}
    c = m.get(g); r = EX['CEM'].get(c) if c else None
    return (r['passed'], r['n']) if r else NA

# ---------------- stress conditions (out of DR), 24 starts
LBL = {'nom_d10': '기준 10 ms', 'nom_d20': '기준 20 ms', 'd25': '지연 25 ms', 'd30': '지연 30 ms', 'd40': '지연 40 ms', 'noise0.1': '각도 노이즈 σ0.1°',
       'noise0.3': '노이즈 σ0.3°', 'noise1.0': '노이즈 σ1.0°', 'zero+1': '진자 영점 +1°', 'zero+2': '영점 +2°', 'zero+3': '영점 +3°', 'zero-1': '영점 -1°', 'zero-3': '영점 -3°', 'noise0.2': '노이즈 σ0.2°', 'zero+5': '영점 +5°', 'zero-5': '영점 -5°', 'enc1024': '진자 엔코더 1024',
       'enc256': '엔코더 256', 'filt0': '속도필터 0 ms', 'filt60': '필터 60 ms', 'filt100': '필터 100 ms', 'drop5': '지령 누락 5%', 'drop15': '누락 15%',
       'drop30': '누락 30%', 'I1.2': '전류 상한 1.2 A', 'I1.0': '전류 상한 1.0 A', 'regen0.5': '회생 한도 0.5 J', 'regen0.3': '회생 한도 0.3 J',
       'mass0.7': '진자 질량×0.7', 'mass1.3': '진자 질량×1.3', 'gam0.6': 'γ×0.6', 'gam1.4': 'γ×1.4', 'alpha0.7': '암 관성×0.7', 'alpha1.4': '암 관성×1.4',
       'coul0': '암 쿨롱 0', 'coul2': '암 쿨롱×2', 'visc0.3': '암 점성×0.3', 'visc3': '암 점성×3', 'stic+100': '정지마찰 +100%', 'stic+200': '정지마찰 +200%',
       'pfric3e-3': '진자 베어링 마찰 3e-3', 'ident08_d10': '비관적 플랜트 10 ms', 'ident08_d20': '비관적 플랜트 20 ms', 'dist_arm0.3': '암 지속 외란 0.3 N·m',
       'dist_arm0.6': '암 외란 0.6 N·m', 'dist_pend2e-3': '진자 지속 외란 2e-3', 'dist_pend5e-3': '진자 외란 5e-3', 'init_arm5': '초기 암 ±5 rad/s',
       'init_pend8': '초기 진자 ±8 rad/s', 'init_near_up': '초기 각도 -170~170°', 'combo': '복합 최악'}
SWC = list(SW)
def stv(k, c, key='passed'):
    r = ST[k].get(c); return (r[key], r['n']) if r else NA

def cell(v): return '미측정' if v is None else f'{v[0]}/{v[1]}'
def rate(v): return np.nan if v is None else v[0] / v[1]

# ================= FIGURE 1: heatmaps
def heat(ax, rows, cols, getter, title, clab):
    M = np.array([[rate(getter(k, c)) for c in cols] for k in rows], float)
    cm = matplotlib.colormaps['RdYlGn'].copy(); cm.set_bad('#d9d9d9')
    ax.imshow(np.ma.masked_invalid(M), cmap=cm, vmin=0, vmax=1, aspect='auto')
    for i, k in enumerate(rows):
        for j, c in enumerate(cols):
            v = getter(k, c); t = '미측정' if v is None else f'{v[0]}'
            ax.text(j, i, t, ha='center', va='center', fontsize=6.5 if v is None else 7.5, color='#333' if v is None or 0.25 < v[0] / v[1] < 0.85 else 'white' if v[0] / v[1] <= 0.25 else 'black')
    ax.set_xticks(range(len(cols))); ax.set_xticklabels(clab, rotation=60, ha='right', fontsize=7.5)
    ax.set_yticks(range(len(rows))); ax.set_yticklabels([LAB1[k] for k in rows], fontsize=8); ax.set_title(title, loc='left', fontsize=10, fontweight='bold')
fig, ax = plt.subplots(figsize=(10, 3.6))
cols = [c for c, _, _ in EXC] + [f'g{g}' for g in GAMS]
def g1(k, c): return gamv(k, float(c[1:])) if c.startswith('g') and c[1].isdigit() else exv(k, c)
heat(ax, ORDER, cols, g1, '그림 1. 학습 무작위화 범위 안의 평가 (기존 원자료, 칸 = 통과 개수, 색 = 통과율)',
     [l + f' ({n})' for _, l, n in EXC] + [f'γ×{g} 20 ms (43)' for g in GAMS])
fig.tight_layout(); fig.savefig(OUT + '/figures/fig1_heatmap_existing.png', dpi=170); plt.close(fig)

fig, ax = plt.subplots(figsize=(13, 3.9))
heat(ax, ORDER, SWC, stv, '그림 2. 학습 범위 밖 스트레스 51조건 (새로 측정, 시작점 24개, 엄격 기준 통과 개수)', [LBL[c] for c in SWC])
fig.tight_layout(); fig.savefig(OUT + '/figures/fig2_heatmap_stress.png', dpi=170); plt.close(fig)

fig, ax = plt.subplots(figsize=(13, 3.9))
heat(ax, ORDER, SWC, lambda k, c: stv(k, c, 'up10'), '그림 3. 같은 51조건에서 "마지막 10 s 동안 |θ|<10°로 서 있음" 개수 (엄격 기준보다 느슨함)', [LBL[c] for c in SWC])
fig.tight_layout(); fig.savefig(OUT + '/figures/fig3_heatmap_upright.png', dpi=170); plt.close(fig)

# ================= FIGURE 4: robustness curves
fig, axs = plt.subplots(1, 5, figsize=(15, 3.2))
def curve(ax, xs, getter, title, xl, xt=None):
    for k in ORDER:
        y = [rate(getter(k, x)) * 100 for x in xs]
        ax.plot(range(len(xs)), y, '-o', ms=3.5, lw=1.6, color=COL[k], label=LAB1[k])
    ax.set_xticks(range(len(xs))); ax.set_xticklabels(xt or xs, fontsize=8); ax.set_ylim(-5, 105); ax.set_title(title, loc='left', fontsize=9.5, fontweight='bold')
    ax.set_xlabel(xl, fontsize=8); ax.grid(alpha=.3)
curve(axs[0], GAMS, lambda k, g: gamv(k, g), '(a) γ 변화, 20 ms (43개)', 'γ 배율 (CEM은 0.8·1.0·1.2만 측정)', [str(g) for g in GAMS])
curve(axs[1], ['nom_d10', 'nom_d20', 'd25', 'd30', 'd40'], stv, '(b) 제어 지연 (24개)', '지연 ms (학습 DR: 10~20)', ['10', '20', '25', '30', '40'])
curve(axs[2], ['zero-5', 'zero-3', 'zero-1', 'nom_d10', 'zero+1', 'zero+2', 'zero+3', 'zero+5'], stv, '(c) 진자 영점 오차', '영점 오차 [°] (학습 DR: ±3°)', ['-5', '-3', '-1', '0', '1', '2', '3', '5'])
curve(axs[3], ['nom_d10', 'noise0.1', 'noise0.2', 'noise0.3', 'noise1.0'], stv, '(d) 각도 측정 노이즈', '노이즈 σ [°]', ['0', '0.1', '0.2', '0.3', '1.0'])
curve(axs[4], ['filt0', 'nom_d10', 'filt60', 'filt100'], stv, '(e) 속도 필터 시정수 (CEM은 미사용)', 'τ [ms] (학습 DR: 0~30)', ['0', '30', '60', '100'])
axs[0].set_ylabel('엄격 기준 통과율 [%]')
axs[4].legend(fontsize=7, loc='center left', bbox_to_anchor=(1.02, 0.5))
fig.suptitle('그림 4. 강건성 곡선', x=0.01, ha='left', fontsize=11, fontweight='bold'); fig.tight_layout(); fig.savefig(OUT + '/figures/fig4_robustness.png', dpi=170); plt.close(fig)

# ================= FIGURE 5: push recovery
PC = [('push_d10', '공칭 10 ms'), ('push_d20', '공칭 20 ms'), ('push_ident08', '비관적 플랜트 10 ms'), ('push_hwlike', '실물형 10 ms')]
PW = [0.5, 1, 1.5, 2, 2.5, 3, 4, 6, 10]
fig, axs = plt.subplots(2, 4, figsize=(13, 5.6), sharey='row')
for i, (c, t) in enumerate(PC):
    for k in ORDER:
        rows = [r for r in ST[k][c]['rows'] if r['dw']]
        inpl = [np.mean([(r['rec'] and not r['fell']) for r in rows if abs(r['dw']) == w]) * 100 for w in PW]
        anyr = [np.mean([r['rec'] for r in rows if abs(r['dw']) == w]) * 100 for w in PW]
        axs[0, i].plot(PW, inpl, '-o', ms=3.5, color=COL[k], label=LAB1[k]); axs[1, i].plot(PW, anyr, '-o', ms=3.5, color=COL[k])
    axs[0, i].set_title(f'{t}', fontsize=9.5, loc='left', fontweight='bold'); axs[1, i].set_xlabel('진자 순간 충격 |Δ(dθ/dt)| [rad/s] (±2방향)', fontsize=8)
    for a in axs[:, i]: a.grid(alpha=.3); a.set_ylim(-5, 105); a.set_xticks(PW)
axs[0, 0].set_ylabel('제자리 복구율 [%]\n(넘어가지 않고 8 s 안 복귀)'); axs[1, 0].set_ylabel('전체 복구율 [%]\n(한 바퀴 돌아 다시 서는 것 포함)')
axs[0, 3].legend(fontsize=7, loc='center left', bbox_to_anchor=(1.02, 0.5))
fig.suptitle('그림 5. 밀기(진자 각속도 순간 충격) 복구 — 직립 4 s 뒤 충격, 이후 10 s', x=0.01, ha='left', fontsize=11, fontweight='bold')
fig.tight_layout(); fig.savefig(OUT + '/figures/fig5_push_recovery.png', dpi=170); plt.close(fig)

# push summary numbers
def push_stats(k, c):
    R = ST[k][c]['rows']; rec = [r for r in R if r['rec']]
    p = [r for r in R if r['dw']]; a = [r for r in R if r['dv']]
    lim = max([w for w in PW if all(r['rec'] and not r['fell'] for r in p if abs(r['dw']) <= w)] or [0])
    alim = max([v for v in (2, 4, 6, 8, 10) if all(r['rec'] and not r['fell'] for r in a if abs(r['dv']) <= v)] or [0])
    return dict(rate=len(rec) / len(R), inplace=sum(r['rec'] and not r['fell'] for r in R) / len(R), t=float(np.mean([r['t'] for r in rec])) if rec else None,
                tmax=max([r['t'] for r in rec]) if rec else None, plim=lim, alim=alim, n=len(R))
PS = {k: {c: push_stats(k, c) for c, _ in PC} for k in ORDER}
REP = {k: ST[k]['repeat'] for k in ORDER}

# ================= FIGURE 6: time / energy / current / compute
COMP = {'CEM': 4.5}   # ms per control step, x86 1 core (CEM_rev22_결과.md); MLP measured below
MLP_MS = float(os.environ.get('MLP_MS', '0.0103'))
for k in ORDER[:-1]: COMP[k] = MLP_MS
fig, axs = plt.subplots(1, 4, figsize=(13, 3.3))
y = np.arange(len(ORDER))
def barh(ax, vals, title, xl, line=None, ltxt=None, fmt='{:.2f}', log=False):
    for i, k in enumerate(ORDER):
        v = vals[k]
        if v is None: ax.text(0, i, ' 미측정', va='center', fontsize=7.5, color='#777'); continue
        ax.barh(i, v, color=COL[k], height=.62); ax.text(v * (1.15 if log else 1) + (0 if log else 0.02 * max(x for x in vals.values() if x)), i, fmt.format(v), va='center', fontsize=7.5)
    ax.set_yticks(y); ax.set_yticklabels([SH[k] for k in ORDER], fontsize=8); ax.invert_yaxis(); ax.set_title(title, loc='left', fontsize=9.5, fontweight='bold'); ax.set_xlabel(xl, fontsize=8)
    if log:
        ax.set_xscale('log'); ax.set_xlim(0.005, 30); ax.set_xticks([0.01, 0.1, 1, 10]); ax.set_xticklabels(['0.01', '0.1', '1', '10'])
    if line: ax.axvline(line, color='#444', ls='--', lw=1); ax.text(line, -0.7, ltxt, fontsize=7, color='#444')
    ax.grid(axis='x', alpha=.3)
barh(axs[0], {k: EX[k]['d10']['reach_mean'] for k in ORDER}, '(a) 평균 도달 시간, 공칭 10 ms', 's (123개)')
NOMC = ['d10', 'd15', 'd20', 'hwlike', 'hwlike_d20', 'mj_d10', 'mj_d20']
barh(axs[1], {k: max(EX[k][c]['regen'] for c in NOMC) for k in ORDER}, '(b) 제동 1회 최대 에너지', 'J (공칭·실물형·MuJoCo 중 최대)', 1.0, '실물 RMD 정지 ≈1 J')
barh(axs[2], {k: ST[k]['nom_d10']['Irms'] for k in ORDER}, '(c) 평균 RMS 전류 (25 s)', 'A, 기준 10 ms 24개', 1.5, '상한 1.5 A')
barh(axs[3], COMP, '(d) 1주기 계산 시간 (x86 1코어)', 'ms (Pi 5 미측정)', 10, '주기 10 ms', fmt='{:.3g}', log=True)
fig.suptitle('그림 6. 시간·에너지·전류·계산량', x=0.01, ha='left', fontsize=11, fontweight='bold'); fig.tight_layout(); fig.savefig(OUT + '/figures/fig6_time_energy.png', dpi=170); plt.close(fig)

# ================= SCORES + radar
GRP = {}
for c, (g, *_r) in SW.items(): GRP.setdefault(g, []).append(c)
def mean_rate(k, items):
    v = [rate(x) for x in items if x is not None]; return float(np.mean(v)) if v else np.nan
SC = {}
for k in ORDER:
    s = {}
    s['공칭 성공'] = mean_rate(k, [exv(k, c) for c in ('d10', 'd15', 'd20', 'mj_d10', 'mj_d20')])
    s['모델 오차 강건성'] = mean_rate(k, [exv(k, c) for c in ('gam08', 'gam12', 'coul05', 'coul125', 'alpha085', 'alpha115', 'swap', 'hwlike', 'hwlike_d20')] +
                              [gamv(k, g) for g in GAMS] + [stv(k, c) for c in GRP['플랜트'] + GRP['비관적 플랜트']])
    s['센서·지연·통신 강건성'] = mean_rate(k, [stv(k, c) for c in GRP['지연(DR 밖)'] + GRP['센서'] + GRP['통신'] + GRP['전원']])
    s['외란·밀기 복구'] = float(np.mean([PS[k][c]['inplace'] * 0.5 + PS[k][c]['rate'] * 0.5 for c, _ in PC] + [REP[k]['up_frac']]))
    s['직립 품질'] = float(np.clip(1 - ST[k]['nom_d10']['wjit'] / 0.5, 0, 1))
    s['에너지 여유'] = float(np.clip(1 - max(EX[k][c]['regen'] for c in NOMC) / 1.0, 0, 1))
    s['계산 여유'] = float(np.clip(1 - COMP[k] / 10, 0, 1))
    SC[k] = s
AX = list(SC['CEM'])
fig = plt.figure(figsize=(11, 6.6))
ang = np.linspace(0, 2 * np.pi, len(AX), endpoint=False).tolist(); ang += ang[:1]
for i, grp in enumerate([['SAC_Py', 'SAC_ML', 'CEM'], ['PPO_ML', 'PPO_Py', 'PPO_Py_own', 'CEM']]):
    ax = fig.add_subplot(1, 2, i + 1, polar=True)
    for k in grp:
        v = [SC[k][a] for a in AX]; v += v[:1]; ax.plot(ang, v, color=COL[k], lw=1.8, label=LAB1[k]); ax.fill(ang, v, color=COL[k], alpha=.08)
    ax.set_xticks(ang[:-1]); ax.set_xticklabels(AX, fontsize=8); ax.set_ylim(0, 1); ax.set_yticks([.25, .5, .75, 1]); ax.set_yticklabels(['.25', '.5', '.75', '1'], fontsize=6)
    ax.legend(fontsize=7.5, loc='upper center', bbox_to_anchor=(0.5, -0.1), ncol=1)
fig.suptitle('그림 7. 기준별 점수 (0~1, 정의는 2절 표 참고) — 왼쪽 SAC vs CEM, 오른쪽 PPO vs CEM', x=0.01, ha='left', fontsize=11, fontweight='bold')
fig.tight_layout(rect=(0, 0, 1, 0.94)); fig.savefig(OUT + '/figures/fig7_radar.png', dpi=170, bbox_inches='tight'); plt.close(fig)

json.dump(dict(scores=SC, push=PS, repeat=REP, comp=COMP), open(OUT + '/selection_summary.json', 'w'), indent=1, ensure_ascii=False)

# ================= markdown tables
L = []
L.append('| 조건 (개수) | ' + ' | '.join(LAB1[k] for k in ORDER) + ' |'); L.append('|---' * (len(ORDER) + 1) + '|')
for c, l, n in EXC: L.append(f'| {l} ({n}) | ' + ' | '.join(cell(exv(k, c)) for k in ORDER) + ' |')
for g in GAMS: L.append(f'| γ×{g}, 20 ms (43) | ' + ' | '.join(cell(gamv(k, g)) for k in ORDER) + ' |')
open(OUT + '/tab_existing.md', 'w').write('\n'.join(L))
L = ['| 묶음 | 조건 | ' + ' | '.join(LAB1[k] for k in ORDER) + ' |', '|---' * (len(ORDER) + 2) + '|']
for c in SWC:
    L.append(f'| {SW[c][0]} | {LBL[c]} | ' + ' | '.join(f"{ST[k][c]['passed']} ({ST[k][c]['up10']})" for k in ORDER) + ' |')
L.append('| 합계 | 엄격 통과 / 1224 (서 있음) | ' + ' | '.join(f"{sum(ST[k][c]['passed'] for c in SWC)} ({sum(ST[k][c]['up10'] for c in SWC)})" for k in ORDER) + ' |')
open(OUT + '/tab_stress.md', 'w').write('\n'.join(L))
L = ['| 조건 | 지표 | ' + ' | '.join(LAB1[k] for k in ORDER) + ' |', '|---' * (len(ORDER) + 2) + '|']
for c, t in PC:
    L.append(f'| {t} | 전체 복구 / 제자리 복구 (28회) | ' + ' | '.join(f"{round(PS[k][c]['rate']*28)} / {round(PS[k][c]['inplace']*28)}" for k in ORDER) + ' |')
    L.append(f'| | 제자리 한계 진자 / 암 [rad/s] | ' + ' | '.join(f"{PS[k][c]['plim']} / {PS[k][c]['alim']}" for k in ORDER) + ' |')
    L.append(f'| | 복구 시간 평균 (최대) [s] | ' + ' | '.join('–' if PS[k][c]['t'] is None else f"{PS[k][c]['t']:.2f} ({PS[k][c]['tmax']:.2f})" for k in ORDER) + ' |')
L.append('| 연속 밀기 (16회×9번) | 직립 시간 비율 / 끝에 서 있음 | ' + ' | '.join(f"{REP[k]['up_frac']*100:.0f}% / {REP[k]['end_up']}/16" for k in ORDER) + ' |')
L.append('| | 인터록 위반 런 | ' + ' | '.join(f"{REP[k]['viol']}" for k in ORDER) + ' |')
open(OUT + '/tab_push.md', 'w').write('\n'.join(L))
L = ['| 기준 | ' + ' | '.join(LAB1[k] for k in ORDER) + ' |', '|---' * (len(ORDER) + 1) + '|']
for a in AX: L.append(f'| {a} | ' + ' | '.join(f'{SC[k][a]:.2f}' for k in ORDER) + ' |')
open(OUT + '/tab_scores.md', 'w').write('\n'.join(L))
L = ['| 지표 | ' + ' | '.join(LAB1[k] for k in ORDER) + ' |', '|---' * (len(ORDER) + 1) + '|']
L.append('| 도달 평균 공칭 10 ms [s] | ' + ' | '.join(f"{EX[k]['d10']['reach_mean']:.2f}" for k in ORDER) + ' |')
L.append('| 도달 평균 실물형 20 ms [s] | ' + ' | '.join(f"{EX[k]['hwlike_d20']['reach_mean']:.2f}" for k in ORDER) + ' |')
L.append('| 직립 진자속도 최대(런 평균), 기준 10 ms [rad/s] | ' + ' | '.join(f"{ST[k]['nom_d10']['wjit']:.2f}" for k in ORDER) + ' |')
L.append('| 직립 진자속도 최대(런 평균), 기준 20 ms [rad/s] | ' + ' | '.join(f"{ST[k]['nom_d20']['wjit']:.2f}" for k in ORDER) + ' |')
L.append('| 직립 RMS 각도 공칭 10 ms [°] | ' + ' | '.join(f"{EX[k]['d10']['rms_bal']:.2f}" for k in ORDER) + ' |')
L.append('| 최대 암 속도 (공칭 3지연) [rad/s] | ' + ' | '.join(f"{max(EX[k][c]['peak_arm'] for c in ('d10','d15','d20')):.1f}" for k in ORDER) + ' |')
L.append('| ±1.5 A 포화율 공칭 10 ms [%] | ' + ' | '.join(f"{EX[k]['d10']['sat_all']:.2f}" for k in ORDER) + ' |')
L.append('| 평균 RMS 전류, 기준 10 ms [A] | ' + ' | '.join(f"{ST[k]['nom_d10']['Irms']:.2f}" for k in ORDER) + ' |')
L.append('| 제동 1회 최대 (공칭·실물형·MuJoCo) [J] | ' + ' | '.join(f"{max(EX[k][c]['regen'] for c in NOMC):.2f}" for k in ORDER) + ' |')
L.append('| 제동 1회 최대 (스트레스 51조건) [J] | ' + ' | '.join(f"{max(ST[k][c]['regen'] for c in SWC):.2f}" for k in ORDER) + ' |')
L.append('| 회생 한도 초과로 모터 정지 (스트레스 1224회 중) | ' + ' | '.join(f"{sum(ST[k][c]['dead'] for c in SWC)}" for k in ORDER) + ' |')
L.append('| 1주기 계산 [ms, x86 1코어] | ' + ' | '.join(f"{COMP[k]:.3g}" for k in ORDER) + ' |')
open(OUT + '/tab_metrics.md', 'w').write('\n'.join(L))
print('ok')
