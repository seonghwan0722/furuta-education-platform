% sac25 (2026-11-23): sac24 settings + v3 stabilizers (merged twin critic, LayerNorm, target every 2, grad clip 10), from sac24 ck_0200 actor.
base='C:/Capstone1/matlab_furuta/results/ppo_swingup_20261119'; addpath('C:/Capstone1/matlab_furuta/rev11');
S=load(fullfile(base,'sac24_rev11_armrate2','config.mat')); cfg=S.cfg; init=load(fullfile(base,'sac24_rev11_armrate2','ck_0200.mat'));
cfg.iters=200; cfg.evalEvery=25; cfg.keepCritics=false; cfg.seed=125; cfg.mergedQ=true; cfg.layerNorm=true; cfg.targetEvery=2; cfg.gradClip=10;
folder=fullfile(base,'sac25_v3_opt'); if ~isfolder(folder), mkdir(folder); end
cfg.init='sac24 ck_0200 actor + v3 stabilizers, fresh critics'; save(fullfile(folder,'config.mat'),'cfg');
cd(folder); sp_sac_v3(folder,init,cfg);
