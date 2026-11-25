% Diagnostic controller: PID swing-up law but NO braking current above 1 rad/s (tests the regeneration hypothesis).
here='C:/Capstone1/matlab_furuta/lmpc_swingup'; addpath(here); addpath('C:/Capstone1/matlab_furuta'); addpath('C:/Capstone1/matlab_furuta/swingup_ppo');
load('C:/Capstone1/matlab_furuta/results/lmpc_swingup_20261120/pid_lqr_design_final.mat','D','g0');
g=g0; g.brakeMax=0; g.brakeV=1;
lm_export_step(D,g,here,'furuta_pid_nobrake_step',"pid"); rehash;
type furuta_pid_nobrake_step.m
root='C:/Capstone1/matlab_furuta'; out=[root '/results/pi_drive20s']; ctrls={'furuta_pid_nobrake_step'};
run([here '/job_pi20.m']);
