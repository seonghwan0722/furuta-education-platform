% PPO on the rev11 hardware-identified plant with the RMD regen-dropout model (budget 0.8 J per braking event).
base='C:/Capstone1/matlab_furuta/results/ppo_swingup_20261119'; addpath('C:/Capstone1/matlab_furuta/rev11');
init=load(fullfile(base,'run7_margin','ck_0250.mat'));
folder=fullfile(base,'run9_rev11_regen'); if ~isfolder(folder), mkdir(folder); end
cfg=sp_default_cfg; cfg.iters=400; cfg.seed=91; cfg.lrA=5e-5; cfg.plantFn='rev11_ident_config';
cfg.dr=struct('filter',true,'delayMax',1,'fracMax',1.0,'alpha',0.15,'coul',0.25,'eta',0.3,'regenBudget',0.8);
cfg.rw.vSoft=9; cfg.rw.arm=0.15; cfg.rw.termPenalty=300; cfg.rw.du=0.05; cfg.rw.regen=2;
cfg.init='run7_margin/ck_0250.mat'; save(fullfile(folder,'config.mat'),'cfg');
sp_ppo2(folder,init,cfg);
