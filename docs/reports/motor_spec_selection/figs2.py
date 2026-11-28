import json, numpy as np, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
FD='/usr/local/lib/python3.13/site-packages/koreanize_matplotlib/fonts/'
for f in ('NanumGothic.ttf','NanumGothicBold.ttf'): fm.fontManager.addfont(FD+f)
plt.rcParams.update({'font.family':'NanumGothic','axes.unicode_minus':False,'font.size':10,
 'axes.edgecolor':'#bbbbbb','axes.labelcolor':'#333','xtick.color':'#555','ytick.color':'#555',
 'axes.spines.top':False,'axes.spines.right':False})
O='/mnt/project-files/motor_report/motor_spec_selection/figures/'
BLUE='#257de0'; ORANGE='#f47230'; TEAL='#00b894'; GRAY='#9aa3ad'; INK='#191919'; GRID='#e6e6e6'
R=json.load(open('/mnt/project-files/motor_report/motor_spec_selection/invdyn.json'))
k='hw1123|sac24_rev11_armrate2/ck_0100'; ts=R[k]['ts']
t=np.array(ts['t'])
# Fig A: time series
fig,ax=plt.subplots(2,1,figsize=(9,5.6),dpi=200,sharex=True,gridspec_kw={'height_ratios':[1.4,1]})
ax[0].plot(t,ts['tau_rmd'],color=BLUE,lw=1.6,label='RMD-X6가 낸 토크 (지령 전류 × 2.1 N·m/A)')
ax[0].plot(t,ts['dd'],color=ORANGE,lw=2,label='같은 움직임에 필요한 부하 토크 (직결 구동)')
ax[0].set_ylabel('토크 [N·m]'); ax[0].set_ylim(-3.6,3.6); ax[0].grid(color=GRID); ax[0].legend(frameon=True,facecolor='white',edgecolor='white',framealpha=0.9,fontsize=9,loc='lower right')
ax[0].set_title('그림 1. 같은 스윙업 동작에서 RMD-X6 토크와 실제 필요한 부하 토크',loc='left',fontsize=12,color=INK,fontweight='bold')
ax[1].plot(t,ts['dd'],color=ORANGE,lw=2); ax[1].axhline(0.2,color='#666',ls='--',lw=1); ax[1].axhline(-0.2,color='#666',ls='--',lw=1)
ax[1].text(3.95,0.21,'설계 피크 0.20 N·m',ha='right',fontsize=8.5,color='#444',va='bottom')
ax[1].set_ylim(-0.3,0.3); ax[1].set_ylabel('부하 토크 확대 [N·m]'); ax[1].set_xlabel('시간 [s] (SAC sac24, 실측 식별 플랜트 hw1123, 매달림 180° 출발)'); ax[1].grid(color=GRID)
ax[1].set_xlim(0,4)
fig.tight_layout(); fig.savefig(O+'figA_torque_timeseries.png'); plt.close(fig)

# Fig B: RMS by component (log)
from matplotlib.patches import Patch
names=[('hw1123|sac24_rev11_armrate2/ck_0100','SAC sac24\n(실물 3/3)'),('hw1123|sac22_rev11_stic2x/ck_0150','SAC sac22\n(실물 3/3)'),('hw1123|run9_rev11_regen/ck_0380','PPO run9\n(실물 통과)')]
fig,ax=plt.subplots(figsize=(9,4.4),dpi=200)
w=0.26
for i,(kk,lab) in enumerate(names):
    r=R[kk]
    for j,(key,c) in enumerate([('gear_fric',GRAY),('gear_inert',BLUE),('load',ORANGE)]):
        v=r[key]['rms']; ax.bar(i+(j-1)*w,v,width=w-0.03,color=c)
        ax.text(i+(j-1)*w,v*1.12,f'{v:.3f}' if v<0.1 else f'{v:.2f}',ha='center',fontsize=8.5,color=INK)
ax.set_xticks(range(3)); ax.set_xticklabels([n[1] for n in names]); ax.set_yscale('log'); ax.set_ylim(0.003,30)
ax.set_yticks([0.01,0.1,1]); ax.set_yticklabels(['0.01','0.1','1'])
ax.set_ylabel('토크 RMS [N·m] (로그 눈금)'); ax.grid(axis='y',color=GRID); ax.set_axisbelow(True)
ax.legend(handles=[Patch(color=GRAY,label='감속기 마찰 (쿨롱 0.785 + 점성 0.186)'),Patch(color=BLUE,label='감속기 반사 관성 (0.025 kg·m²)'),Patch(color=ORANGE,label='암·진자 부하 (직결 시 필요)')],loc='upper right',frameon=False,fontsize=8.5)
ax.set_title('그림 2. RMD-X6 토크의 성분별 크기: 부하 몫은 약 1/100',loc='left',fontsize=12,color=INK,fontweight='bold')
fig.tight_layout(); fig.savefig(O+'figB_decomposition.png'); plt.close(fig)

# Fig C: cost vs peak torque
C=[('RMD-X6-P20 (기준)',1038600,50,'ref'),('RMD-L-5010-35T',133000,0.65,'pick'),('GL35 KV100',196800,0.46,'ok'),('GL40 KV70',167200,0.50,'ok'),
   ('OT4307',212800,0.45,'ok'),('MHF5005',172800,0.40,'ok'),('GM5208-12',133800,0.25,'marg'),('GM3506',105700,0.10,'fail'),('GM2804',90000,0.034,'fail')]
col={'ref':GRAY,'pick':ORANGE,'ok':BLUE,'marg':'#f2a600','fail':'#c0c6cc'}
fig,ax=plt.subplots(figsize=(9.5,5.4),dpi=200)
ax.axhspan(0.2,100,color='#eaf3fb',zorder=0); ax.axhline(0.2,color='#666',ls='--',lw=1.2)
ax.text(1.3e6,0.215,'요구 피크 0.20 N·m (부하 0.13 × 1.5)',ha='right',fontsize=9,color='#444')
ax.axhline(0.13,color='#999',ls=':',lw=1); ax.text(1.3e6,0.118,'부하 최대 0.13 N·m',ha='right',fontsize=8.5,color='#666',va='top')
for n,cost,tq,k in C:
    ax.scatter(cost/1e4,tq,s=110 if k=='pick' else 60,color=col[k],edgecolor='white',linewidth=1.5,zorder=3)
off={'RMD-L-5010-35T':(-12,18),'GL35 KV100':(6,22),'GL40 KV70':(-4,30),'OT4307':(10,-8),'MHF5005':(10,-26),'GM5208-12':(12,-4),'GM3506':(10,-10),'GM2804':(10,-4),'RMD-X6-P20 (기준)':(-10,-14)}
for n,cost,tq,k in C:
    dx,dy=off[n]; ax.annotate(f'{n}\n₩{cost/1e4:.1f}만',(cost/1e4,tq),xytext=(dx,dy),textcoords='offset points',arrowprops=dict(arrowstyle='-',color='#aaa',lw=0.6),fontsize=8.5,color=INK,ha='left' if dx>0 else 'right',fontweight='bold' if k=='pick' else 'normal')
ax.set_xscale('log'); ax.set_yscale('log'); ax.set_xlim(7,140); ax.set_ylim(0.02,100)
ax.set_xticks([10,20,50,100]); ax.set_xticklabels(['10만','20만','50만','100만'])
ax.set_yticks([0.03,0.1,0.3,1,3,10,30,100]); ax.set_yticklabels(['0.03','0.1','0.3','1','3','10','30','100'])
ax.set_xlabel('구동계 비용 [원] (모터 + 필요한 드라이버·엔코더·MCU, 로그 눈금)'); ax.set_ylabel('피크 토크 [N·m] (로그 눈금)')
ax.grid(color=GRID,which='major'); ax.set_axisbelow(True)
ax.legend(handles=[Patch(color=ORANGE,label='선정'),Patch(color=BLUE,label='요구 충족'),Patch(color='#f2a600',label='경계 (상한값 기준 충족)'),Patch(color='#c0c6cc',label='미달'),Patch(color=GRAY,label='연구실 기준 모터')],loc='upper left',frameon=False,fontsize=8.5)
ax.set_title('그림 3. 후보 모터의 비용 대비 피크 토크',loc='left',fontsize=12,color=INK,fontweight='bold')
fig.tight_layout(); fig.savefig(O+'figC_cost_torque.png'); plt.close(fig)
print('ok')
