% SAC speed/stability benchmark (2026-11-23): same init, same env/reward as sac24, fresh critics, 100 iterations.
% variant 'base' = v2 behaviour, 'opt' = merged twin critic + LayerNorm + target every 2 + grad clip 10.
base='C:/Capstone1/matlab_furuta/results/ppo_swingup_20261119'; addpath('C:/Capstone1/matlab_furuta/rev11');
S=load(fullfile(base,'sac24_rev11_armrate2','config.mat')); cfg=S.cfg;
init=load(fullfile(base,'sac19_rev11_regen','ck_0150.mat'));
cfg.iters=100; cfg.evalEvery=25; cfg.keepCritics=false; cfg.seed=200+seedOff;
if any(strcmp(variant,{'opt','fast'})), cfg.mergedQ=true; cfg.layerNorm=true; cfg.targetEvery=2; cfg.gradClip=10; end
if strcmp(variant,'fast'), cfg.updatesPerIter=64; cfg.batch=1024; end   % 4x fewer, 4x larger updates (same samples seen)
folder=fullfile(base,['bench_sac_' variant '_s' num2str(seedOff)]); if ~isfolder(folder), mkdir(folder); end
cfg.init=['bench: sac19 ck_0150 actor, fresh critics, sac24 env/reward, variant ' variant]; save(fullfile(folder,'config.mat'),'cfg');
cd(folder); sp_sac_v3(folder,init,cfg);
