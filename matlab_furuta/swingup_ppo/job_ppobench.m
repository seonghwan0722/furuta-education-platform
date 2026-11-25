% PPO benchmark (2026-11-23): run12 config from run10 ck_0250, 150 iterations; 'opt' = linear LR annealing + grad-norm clip 0.5.
base='C:/Capstone1/matlab_furuta/results/ppo_swingup_20261119'; addpath('C:/Capstone1/matlab_furuta/rev11');
S=load(fullfile(base,'run12_rev11_hold_lo','config.mat')); cfg=S.cfg; init=load(fullfile(base,'run10_rev11_bias','ck_0250.mat'));
cfg.iters=150; cfg.seed=300+seedOff;
if strcmp(variant,'opt'), cfg.lrAnneal=true; cfg.gradClip=0.5; end
folder=fullfile(base,['bench_ppo_' variant '_s' num2str(seedOff)]); if ~isfolder(folder), mkdir(folder); end
cfg.init=['bench: run10 ck_0250, run12 config, variant ' variant]; save(fullfile(folder,'config.mat'),'cfg');
tic; sp_ppo2(folder,init,cfg); fprintf('WALL %.1f s\n',toc);
