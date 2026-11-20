here='C:/Capstone1/matlab_furuta/lmpc_swingup'; addpath(here); addpath('C:/Capstone1/matlab_furuta'); addpath('C:/Capstone1/matlab_furuta/swingup_ppo');
load('C:/Capstone1/matlab_furuta/results/lmpc_swingup_20261120/pid_lqr_design_final.mat','D','g0');
g=g0; g.brakeMax=0; g.brakeV=1; g.brakeMaxBal=0.33; g.brakeVBal=4; g.capRate=4.5; g.thOffsetDeg=2.77;
if ~exist('stepName','var'), stepName='furuta_pid_r5_step'; end
lm_export_step(D,g,here,stepName,"pid"); rehash;
L=readlines(fullfile(here,[stepName '.m'])); disp(L(contains(L,"bal &&") | contains(L,"cap=")));
root='C:/Capstone1/matlab_furuta'; out=[root '/results/pi_drive20s']; ctrls={stepName};
run([here '/job_pi20.m']);
