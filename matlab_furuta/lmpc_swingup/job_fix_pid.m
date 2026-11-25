here='C:/Capstone1/matlab_furuta/lmpc_swingup'; addpath(here); addpath('C:/Capstone1/matlab_furuta'); addpath('C:/Capstone1/matlab_furuta/swingup_ppo');
out='C:/Capstone1/matlab_furuta/results/lmpc_swingup_20261120/';
xr=[zeros(1,3); deg2rad([180 175 -175]); zeros(2,3)];
for sd=[3001 3002], rng(sd,'twister'); n=5; xr=[xr [pi*(2*rand(1,n)-1); pi+deg2rad(30)*(2*rand(1,n)-1); 0.5*(2*rand(1,n)-1); 1*(2*rand(1,n)-1)]]; end %#ok<AGROW>
t0=tic; M=lm_fixed_eval('furuta_pid_step',xr,25);
M.InitArmRad=xr(1,:)'; M.InitArmRate=xr(3,:)'; M.InitPendRate=xr(4,:)';
writetable(M,[out 'fixed_mil_pid.csv']); fprintf('pid FIXED %d/%d in %.0f s\n',nnz(M.Passed),height(M),toc(t0));
