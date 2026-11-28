% rev22 PPO started from the rev22 SAC actor (2026-11-28). The run10-lineage PPO actor keeps a pendulum-rate spike
% (0.6-0.9 rad/s) at upright on rev22 whatever the reward/lr; the SAC mean network (same 5-64-64-1 tanh shape) does not.
% init = sac_rev22_v3 ck_0050 (actor = deterministic SAC mean, critic = PPO critic carried in the checkpoint, bank),
% run12 cfg + hold 3 / wUp 0.05 / vUp 0.2, critic warm-up 40 it, std0 0.1. cfg.dr.gam=0.2;
root='C:/Capstone1/matlab_furuta'; addpath(root); addpath([root '/swingup_ppo']); addpath([root '/rev11']); addpath([root '/rev22']);
base=[root '/results/ppo_swingup_20261119']; init=load([root '/results/rev22_rl_20261127/sac_rev22_v3/ck_0050.mat']);
S=load(fullfile(base,'run12_rev11_hold_lo','config.mat')); cfg=S.cfg;
cfg.plantFn='rev22_hw_config'; cfg.iters=300; cfg.seed=2210; cfg.rw.hold=3.0; cfg.rw.wUp=0.05; cfg.rw.vUp=0.2;
cfg.criticWarmup=40; cfg.std0=0.1; cfg.keepStd=false; cfg.dr.gam=0.2;
folder=[root '/results/rev22_rl_20261127/ppo_rev22_sacinitg']; if ~isfolder(folder), mkdir(folder); end
cfg.init='sac_rev22_v3/ck_0050 actor + run12 cfg + hold3/wUp.05/vUp.2 + criticWarmup 40 + std0 0.1 cfg.dr.gam=0.2;'; save(fullfile(folder,'config.mat'),'cfg');
t0=tic; sp_ppo2(folder,init,cfg); fprintf('PPO_DONE %.0f s\n',toc(t0));
