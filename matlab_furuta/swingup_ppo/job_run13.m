% PPO hold-quality fine-tune (2026-11-22): from run10 ck_0250; adds arm stiction, stronger pendulum bearing friction,
% rest-at-bottom starts and hold rewards (success-region bonus, pend-rate and arm-rate penalties near upright)
% against the slow 0.7-1 Hz balance oscillation seen on hardware.
base='C:/Capstone1/matlab_furuta/results/ppo_swingup_20261119'; addpath('C:/Capstone1/matlab_furuta/rev11');
init=load(fullfile(base,'run12_rev11_hold_lo','ck_0300.mat'));
folder=fullfile(base,'run13_rev11_delay'); if ~isfolder(folder), mkdir(folder); end
cfg=sp_default_cfg; cfg.iters=300; cfg.seed=113; cfg.lrA=5e-5; cfg.plantFn='rev11_ident_config';
cfg.mix=[0.35 0.30 0.20 0.05 0.10];
cfg.dr=struct('filter',true,'delayMax',2,'fracMax',1.0,'alpha',0.15,'coul',0.25,'eta',0.3,'regenBudget',0.8,'biasDeg',3,'coulThMax',2e-3,'stictionMax',0.5);
cfg.rw.vSoft=9; cfg.rw.arm=0.15; cfg.rw.termPenalty=300; cfg.rw.du=0.05; cfg.rw.regen=2;
cfg.rw.hold=0.3; cfg.rw.wUp=0.01; cfg.rw.vUp=0.01;   % lowered after run11 lost delay robustness
cfg.init='run10_rev11_bias/ck_0250.mat + stiction/bearing friction/rest starts run12 ck_0300 + whole-step delay randomization 10-20 ms (delayMax 2) to recover delay robustness (run13)'; save(fullfile(folder,'config.mat'),'cfg');
sp_ppo2(folder,init,cfg);
