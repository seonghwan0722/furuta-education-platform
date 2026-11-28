% rev22 SAC (2026-11-27): sac25_v3_opt recipe (sac24 reward vUp 0.2 + merged twin critic/LayerNorm/target 2/clip 10)
% on the rev22 plant, from sac24_rev11_armrate2 ck_0200 actor (as sac25), fresh critics. Python twin: rev22_rl/train_rev22.py sac.
root='C:/Capstone1/matlab_furuta'; addpath(root); addpath([root '/swingup_ppo']); addpath([root '/rev11']); addpath([root '/rev22']);
base=[root '/results/ppo_swingup_20261119'];
S=load(fullfile(base,'sac25_v3_opt','config.mat')); cfg=S.cfg; init=load(fullfile(base,'sac24_rev11_armrate2','ck_0200.mat'));
cfg.plantFn='rev22_hw_config'; cfg.iters=200; cfg.evalEvery=25; cfg.seed=2202;
folder=[root '/results/rev22_rl_20261127/sac_rev22_v3']; if ~isfolder(folder), mkdir(folder); end
cfg.init='sac24 ck_0200 actor + sac25 v3 cfg, fresh critics, plant rev22_hw_config'; save(fullfile(folder,'config.mat'),'cfg');
t0=tic; cd(folder); sp_sac_v3(folder,init,cfg); fprintf('SAC_DONE %.0f s\n',toc(t0));
