% rev22 PPO reward variant 'wup' (2026-11-27): run12 recipe on rev22 produced a fast small-amplitude chatter at upright
% (|theta|<1.5 deg but |theta_dot| ~0.7 rad/s > 0.5 strict limit). Variant raises near-upright penalties: cfg.rw.wUp=0.05;
root='C:/Capstone1/matlab_furuta'; addpath(root); addpath([root '/swingup_ppo']); addpath([root '/rev11']); addpath([root '/rev22']);
base=[root '/results/ppo_swingup_20261119']; init=load(fullfile(base,'run10_rev11_bias','ck_0250.mat'));
S=load(fullfile(base,'run12_rev11_hold_lo','config.mat')); cfg=S.cfg;
cfg.plantFn='rev22_hw_config'; cfg.iters=300; cfg.seed=2203; cfg.rw.wUp=0.05;
folder=[root '/results/rev22_rl_20261127/ppo_rev22_wup']; if ~isfolder(folder), mkdir(folder); end
cfg.init='run10_rev11_bias/ck_0250 + run12 cfg + wup, plant rev22_hw_config'; save(fullfile(folder,'config.mat'),'cfg');
t0=tic; sp_ppo2(folder,init,cfg); fprintf('PPO_DONE %.0f s\n',toc(t0));
