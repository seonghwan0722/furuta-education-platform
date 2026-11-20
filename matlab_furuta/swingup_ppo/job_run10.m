% PPO fine-tune from run9 ck_0380 with pendulum zero-error (+-3 deg) and bearing friction randomization (hardware 2026-11-20).
base='C:/Capstone1/matlab_furuta/results/ppo_swingup_20261119'; addpath('C:/Capstone1/matlab_furuta/rev11');
init=load(fullfile(base,'run9_rev11_regen','ck_0380.mat'));
folder=fullfile(base,'run10_rev11_bias'); if ~isfolder(folder), mkdir(folder); end
cfg=sp_default_cfg; cfg.iters=300; cfg.seed=101; cfg.lrA=5e-5; cfg.plantFn='rev11_ident_config';
cfg.dr=struct('filter',true,'delayMax',1,'fracMax',1.0,'alpha',0.15,'coul',0.25,'eta',0.3,'regenBudget',0.8,'biasDeg',3,'coulThMax',1e-3);
cfg.rw.vSoft=9; cfg.rw.arm=0.15; cfg.rw.termPenalty=300; cfg.rw.du=0.05; cfg.rw.regen=2;
cfg.init='run9_rev11_regen/ck_0380.mat + zero-error/bearing-friction randomization'; save(fullfile(folder,'config.mat'),'cfg');
sp_ppo2(folder,init,cfg);
