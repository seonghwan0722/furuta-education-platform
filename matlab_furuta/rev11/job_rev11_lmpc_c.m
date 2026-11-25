% LMPC rev11c (2026-11-22): rev11b + observer qObs [200 800]->[50 200] + balance-only command slew 0.3 (against chatter)
root='C:/Capstone1/matlab_furuta'; here=[root '/lmpc_swingup']; addpath(root); addpath([root '/swingup_ppo']); addpath(here); addpath([root '/rev11']);
B=load([root '/rev11/rev11_design_b.mat']); cp=B.cp; g=B.g;
D=lm_design(qObs=[50 200],fc=0,vmax=13.5,plantCfg=cp,Q=[3 10 5 5]); g.slewBal=0.3;
save([root '/rev11/rev11_design_c.mat'],'D','g','cp');
g.thOffsetDeg=2.77; lm_export_step(D,g,here,'furuta_lmpc_rev11c_step',"lmpc"); rehash;
