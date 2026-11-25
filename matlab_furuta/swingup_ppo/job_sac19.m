base='C:/Capstone1/matlab_furuta/results/ppo_swingup_20261119';
addpath('C:/Capstone1/matlab_furuta/rev11'); init=load(fullfile(base,'sac18_taurand','ck_0450.mat'));
folder=fullfile(base,'sac19_rev11_regen'); if ~isfolder(folder), mkdir(folder); end
cfg=struct('seed',119,'nEnv',8,'episodeSeconds',10,'iters',500,'stepsPerIter',32,'updatesPerIter',256,'batch',256, ...
 'buffer',1e6,'gamma',0.99,'tau',0.005,'lrQ',3e-4,'lrA',3e-4,'lrAlpha',3e-4,'alpha0',0.5,'autoAlpha',true,'targetEnt',-1, ...
 'std0',0.3,'actorWarmup',30,'actorEvery',1,'evalEvery',50,'mix',[0.45 0.30 0.20 0.05],'bcW',0.5,'bcDecay',300,'bcMin',0,'keepCritics',true,'nstep',3,'noiseRho',0.9);
cfg.dr=struct('filter',true,'delayMax',1,'fracMax',1.0,'alpha',0.15,'coul',0.25,'eta',0.3,'tauRange',[0 0.03],'regenBudget',0.8); cfg.plantFn='rev11_ident_config';
d=sp_default_cfg; cfg.rw=d.rw; cfg.rw.vSoft=9; cfg.rw.arm=0.15; cfg.rw.termPenalty=100; cfg.rw.du=0.05; cfg.armLimTrain=15;
cfg.rw.hold=3.0; cfg.rw.wUp=0.05; cfg.rw.regen=2;
cfg.init='sac18_taurand/ck_0450.mat on rev11 ident plant + regen dropout model'; save(fullfile(folder,'config.mat'),'cfg');
cd(folder); sp_sac_v2(folder,init,cfg);
