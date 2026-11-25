addpath('C:/Capstone1/matlab_furuta'); addpath('C:/Capstone1/matlab_furuta/lmpc_swingup');
cd('C:/Capstone1/matlab_furuta/results/lmpc_swingup_20261120/pi_models/furuta_pid_bal_step');
load_system('furuta_pi_hardware_controller.slx'); m='furuta_pi_hardware_controller'; cfg=getActiveConfigSet(m);
fprintf('HardwareBoard: %s\n',get_param(m,'HardwareBoard'));
for p=["BoardParameters.DeviceAddress","BoardParameters.Username","CAN.BusSpeed0"]
  try, v=codertarget.data.getParameterValue(cfg,char(p)); fprintf('%s = %s\n',p,string(v)); catch e, fprintf('%s : %s\n',p,e.message); end
end
close_system(m,0);
