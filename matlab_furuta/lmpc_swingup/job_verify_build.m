addpath('C:/Capstone1/matlab_furuta'); out='C:/Capstone1/runs_pid/verify'; cd(out);
f=build_furuta_pi_hardware(Verification=true,Folder=out); load_system(f); [~,m]=fileparts(f); cfg=getActiveConfigSet(m);
fprintf('VERIFY %s CAN %s addr %s\n',m,string(codertarget.data.getParameterValue(cfg,'CAN.BusSpeed0')),string(codertarget.data.getParameterValue(cfg,'BoardParameters.DeviceAddress')));
names=find_system(m,'BlockType','Outport'); disp(names);
save_system(m); close_system(m,0);
