% LMPC rev11 retune (2026-11-22): Q arm 10->3, arm rate 1->5, pend rate 1->5 against the slow ~1 Hz balance
% oscillation seen on hardware (reproduced in sim with pendulum bearing friction + 1 deg zero error + arm stiction).
root='C:/Capstone1/matlab_furuta'; here=[root '/lmpc_swingup']; addpath(root); addpath([root '/swingup_ppo']); addpath(here); addpath([root '/rev11']);
load([root '/results/lmpc_swingup_20261120/pid_lqr_design_final.mat'],'g0');
cp=rev11_ident_config(); L=load([root '/rev11/rev11_design.mat']); g=L.g;
D=lm_design(qObs=[200 800],fc=0,vmax=13.5,plantCfg=cp,Q=[3 10 5 5]);
save([root '/rev11/rev11_design_b.mat'],'D','g','cp');
xr=[]; for sd=[2001 2002], rng(sd,'twister'); xr=[xr [pi*(2*rand(1,20)-1); pi+deg2rad(30)*(2*rand(1,20)-1); 0.5*(2*rand(1,20)-1); 1*(2*rand(1,20)-1)]]; end
x0=[[zeros(1,3); deg2rad([180 175 -175]); zeros(2,3)] xr];
evb=struct('filter',true,'delay',1,'armLim',15,'pendLim',25,'frac',0,'plantCfg',cp);
for cond=1:3
  ev=evb; if cond>=2, ev.stic=0.5; ev.biasDeg=1; ev.coulTh=1e-3; end; if cond==3, ev.frac=1; ev.biasDeg=-1; end
  for DD={L.D,D}
    gg=g; gg.balance="lmpc"; [M,R]=lm_eval(DD{1},gg,x0,20,ev); S=bal_metric(R,max(4,0));
    fprintf('CHECKB cond %d Q=%s: pass %d/43, strict(obs) >=5s %d/43, meanReach %.2f, maxArm %.1f, maxPend %.1f\n',cond,mat2str(DD{1}.opts.Q),nnz(M.Passed),nnz(S(:,1)>=5),mean(M.ReachTime(M.Passed)),max(M.PeakArmRate),max(M.PeakPendRate));
  end
end
g.thOffsetDeg=2.77;
lm_export_step(D,g,here,'furuta_lmpc_rev11b_step',"lmpc"); rehash;
