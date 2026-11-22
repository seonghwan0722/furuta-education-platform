% SAC on rev11 plant + regen dropout + pendulum zero-error (+-3 deg) and pendulum bearing friction randomization.
% Reason: hardware 2026-11-20 sac19 ck_0100 reached upright 4x but could not hold; sim shows it fails with +-2 deg zero error.
base='C:/Capstone1/matlab_furuta/results/ppo_swingup_20261119';
addpath('C:/Capstone1/matlab_furuta/rev11'); init=load(fullfile(base,initDir,initCk));
folder=fullfile(base,outDir); if ~isfolder(folder), mkdir(folder); end
cfg=struct('seed',123,'nEnv',8,'episodeSeconds',10,'iters',400,'stepsPerIter',32,'updatesPerIter',256,'batch',256, ...
 'buffer',1e6,'gamma',0.99,'tau',0.005,'lrQ',3e-4,'lrA',3e-4,'lrAlpha',3e-4,'alpha0',0.5,'autoAlpha',true,'targetEnt',-1, ...
 'std0',0.3,'actorWarmup',30,'actorEvery',1,'evalEvery',50,'mix',[0.30 0.30 0.20 0.05 0.15],'bcW',0.5,'bcDecay',300,'bcMin',0,'keepCritics',true,'nstep',3,'noiseRho',0.9);
cfg.dr=struct('filter',true,'delayMax',1,'fracMax',1.0,'alpha',0.15,'coul',0.25,'eta',0.3,'tauRange',[0 0.03],'regenBudget',0.8,'biasDeg',3,'coulThMax',1e-3,'stictionMax',1.0); cfg.plantFn='rev11_ident_config';
d=sp_default_cfg; cfg.rw=d.rw; cfg.rw.vSoft=9; cfg.rw.arm=0.15; cfg.rw.termPenalty=100; cfg.rw.du=0.05; cfg.armLimTrain=15;
cfg.rw.hold=3.0; cfg.rw.wUp=0.05; cfg.rw.regen=2; cfg.rw.vUp=0.03;   % sac23: stop the arm spinning while balancing (hardware sac22)
cfg.init=['sac19_rev11_regen/' initCk ' + zero-error/bearing-friction randomization']; save(fullfile(folder,'config.mat'),'cfg');
cd(folder); sp_sac_v2(folder,init,cfg);
