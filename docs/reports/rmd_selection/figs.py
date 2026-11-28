import json, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
FD='/usr/local/lib/python3.13/site-packages/koreanize_matplotlib/fonts/'
for f in ('NanumGothic.ttf','NanumGothicBold.ttf'): fm.fontManager.addfont(FD+f)
plt.rcParams.update({'font.family':'NanumGothic','axes.unicode_minus':False,'font.size':10,'font.weight':'normal',
 'axes.edgecolor':'#bbbbbb','axes.labelcolor':'#333','xtick.color':'#555','ytick.color':'#555',
 'axes.spines.top':False,'axes.spines.right':False})
OUT='/mnt/project-files/motor_report/rmd_selection/figures/'
SIM='#f47230'; EXP='#257de0'; SPEC='#00b894'; INK='#191919'; GRID='#e6e6e6'
CAT={'sim':SIM,'exp':EXP,'spec':SPEC}
LAB={'sim':'시뮬레이션 요구값 (rev11 MuJoCo)','exp':'실험값 (연구실 RMD-X6 실물)','spec':'모터 사양 (RMD-X6-P20-60-E)'}
def legend(ax,loc='lower right'):
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=CAT[k],label=LAB[k]) for k in ('sim','exp','spec')],loc='upper center',bbox_to_anchor=(0.35,-0.13),ncol=3,frameon=False,fontsize=9)

# Fig1 torque
rows=[('sim','스윙업 최소 성립 토크 (마찰 기본, 4.8 s)',0.5),
 ('sim','스윙업 약 2 s 토크 (마찰 기본)',1.0),
 ('sim','스윙업 최소 성립 토크 (마찰 8배)',1.0),
 ('exp','정지마찰 (전류 시험, 0.3 A)',0.3*2.1),
 ('exp','식별 쿨롱 마찰 (hw1123)',0.785),
 ('exp','직립 유지 구간 최대 지령 (PPO, 0.87 A)',0.87*2.1),
 ('exp','실물 운용 상한 = 스윙업 포화 (1.5 A)',1.5*2.1),
 ('spec','정격 토크 (9.5 A)',20),
 ('spec','피크 토크 (29.1 A, 표기 50~60)',50)]
fig,ax=plt.subplots(figsize=(9,5.1),dpi=200)
y=list(range(len(rows)))[::-1]
for yi,(k,l,v) in zip(y,rows):
    ax.barh(yi,v,color=CAT[k],height=0.62)
    ax.text(v*1.08,yi,f'{v:.2f} N·m' if v<10 else f'{v:.0f} N·m',va='center',fontsize=9,color=INK)
ax.set_yticks(y); ax.set_yticklabels([r[1] for r in rows],fontsize=9)
ax.set_xscale('log'); ax.set_xlim(0.1,200); ax.set_xlabel('출력축 토크 [N·m] (로그 눈금)')
ax.grid(axis='x',color=GRID,which='both'); ax.set_axisbelow(True)
ax.set_title('그림 1. 토크: 시뮬레이션 요구값 · 실험값 · 모터 사양',loc='left',fontsize=12,color=INK,fontweight='bold')
ax.set_xticks([0.1,1,10,100]); ax.set_xticklabels(['0.1','1','10','100'])
legend(ax,'upper right'); fig.tight_layout(); fig.savefig(OUT+'fig1_torque.png'); plt.close(fig)

# Fig2 speed
rows=[('sim','스윙업 1 N·m 시 암 최고속도',9.05),('sim','스윙업 2 N·m 시 암 최고속도',10.40),('sim','스윙업 4 N·m 시 암 최고속도 (마찰 8배)',18.0),
 ('exp','0.5 A 정속 회전 (pi_current_06)',2.35),('exp','PPO run10 스윙업 최고 (그래프 판독)',9.3),('exp','PPO run9 스윙업 최고 (그래프 판독)',9.5),
 ('exp','SAC sac19 스윙업 최고 (로그)',11.5),('exp','LMPC 스윙업 최고 (그래프 판독)',13.0),
 ('spec','정격 속도 153 rpm',153*2*3.14159/60),('spec','무부하 속도 176 rpm',176*2*3.14159/60)]
fig,ax=plt.subplots(figsize=(9,5.3),dpi=200)
y=list(range(len(rows)))[::-1]
for yi,(k,l,v) in zip(y,rows):
    ax.barh(yi,v,color=CAT[k],height=0.62); ax.text(v+0.25,yi,f'{v:.1f}',va='center',fontsize=9,color=INK)
ax.axvline(15,color='#666',ls='--',lw=1.2); ax.text(15.1,len(rows)-0.45,'인터록 15 rad/s',fontsize=8.5,color='#444')
ax.set_yticks(y); ax.set_yticklabels([r[1] for r in rows],fontsize=9)
ax.set_xlim(0,21); ax.set_xlabel('암(출력축) 각속도 [rad/s]'); ax.grid(axis='x',color=GRID); ax.set_axisbelow(True)
ax.set_title('그림 2. 암 각속도: 시뮬레이션 요구값 · 실험값 · 모터 사양',loc='left',fontsize=12,color=INK,fontweight='bold')
legend(ax,'lower right'); fig.tight_layout(); fig.savefig(OUT+'fig2_speed.png'); plt.close(fig)

# Fig3 current tracking
fig,ax=plt.subplots(figsize=(6.2,4.6),dpi=200)
cmd=[0.1,0.3,0.5]; meas=[0.095,0.294,0.495]
ax.plot([0,0.6],[0,0.6],color='#999',lw=1.2,ls='--'); ax.text(0.47,0.53,'지령 = 응답',fontsize=8.5,color='#666',rotation=37)
ax.errorbar([0.3],[0.285],yerr=[[0.035],[0.035]],fmt='none',ecolor=EXP,elinewidth=2,capsize=5)
ax.scatter(cmd,meas,s=60,color=EXP,zorder=3,edgecolor='white',linewidth=1.5)
for c,m,t in zip(cmd,meas,['0.095 A (정지)','0.294 A (정지)','0.495 A (회전 22 rpm)']):
    ax.annotate(t,(c,m),xytext=(8,-14),textcoords='offset points',fontsize=9,color=INK)
ax.text(0.33,0.215,'pi_current_05: 0.25~0.32 A',fontsize=8.5,color='#444')
ax.axvspan(0,0.3,color='#f2f2f2',zorder=0); ax.text(0.01,0.56,'정지마찰 구간 (≤0.3 A ≈ 0.63 N·m)',fontsize=8.5,color='#555')
ax.set_xlim(0,0.6); ax.set_ylim(0,0.6); ax.set_xlabel('Pi 전류 지령 (0xA1) [A]'); ax.set_ylabel('RMD 보고 전류 (평균) [A]')
ax.grid(color=GRID); ax.set_axisbelow(True)
ax.set_title('그림 3. 전류 지령 대비 RMD 응답 (실험값)',loc='left',fontsize=12,color=INK,fontweight='bold')
fig.tight_layout(); fig.savefig(OUT+'fig3_current.png'); plt.close(fig)

# Fig4 torque-speed plane
ct=json.load(open('/mnt/project-files/motor_sizing_rev11/rmd_ct.json'))
fig,ax=plt.subplots(figsize=(8,5),dpi=200)
wr=153*2*3.14159/60; w0=176*2*3.14159/60
ax.fill_between([0,wr],0,20,color=SPEC,alpha=0.18,lw=0); ax.plot([0,wr,wr],[20,20,0],color=SPEC,lw=2)
ax.plot([0,wr],[50,50],color=SPEC,lw=2,ls=':'); ax.axvline(w0,color=SPEC,lw=1.2,ls='--')
ax.text(0.3,21.5,'정격 영역 (20 N·m, 16.0 rad/s)',fontsize=9,color=INK); ax.text(0.3,51.5,'피크 50 N·m (단시간)',fontsize=9,color=INK)
ax.text(w0+0.15,30,'무부하\n18.4 rad/s',fontsize=8.5,color=INK)
ax.add_patch(plt.Rectangle((0,0),13,3.15,facecolor=EXP,alpha=0.35,edgecolor=EXP,lw=2))
ax.text(0.3,4.2,'실물 운용 영역 (≤3.15 N·m, ≤13 rad/s)',fontsize=9,color=INK)
xs=[r['best']['peak_w'] for r in ct if r['best']]; ys=[r['best']['peak_u'] for r in ct if r['best']]
ax.scatter(xs,ys,s=50,color=SIM,zorder=4,edgecolor='white',linewidth=1.5,label='시뮬레이션 스윙업 성공 사례 (최대 토크, 최고 암속도)')
ax.axvline(15,color='#666',ls='--',lw=1); ax.text(14.2,24,'인터록 15',fontsize=8.5,color='#444',rotation=90)
ax.set_xlim(0,21); ax.set_ylim(0,58); ax.set_xlabel('암 각속도 [rad/s]'); ax.set_ylabel('출력축 토크 [N·m]')
ax.grid(color=GRID); ax.set_axisbelow(True)
from matplotlib.patches import Patch
ax.legend(handles=[Patch(color=SIM,label=LAB['sim']+' 성공 사례'),Patch(color=EXP,alpha=0.5,label=LAB['exp']+' 운용 영역'),Patch(color=SPEC,alpha=0.5,label=LAB['spec']+' 정격 영역')],loc='upper right',frameon=False,fontsize=8.5,bbox_to_anchor=(1,0.80))
ax.set_title('그림 4. 토크–속도 평면에서 본 운용점과 모터 사양',loc='left',fontsize=12,color=INK,fontweight='bold')
fig.tight_layout(); fig.savefig(OUT+'fig4_torque_speed.png'); plt.close(fig)
print('done')
