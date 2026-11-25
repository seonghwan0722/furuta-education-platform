% Build, deploy and run a Pi model in external mode (Monitor & Tune) from batch, then save telemetry.
% Inputs (workspace): modelDir, modelName, runSeconds, runTag
addpath('C:/Capstone1/matlab_furuta'); addpath('C:/Capstone1/matlab_furuta/lmpc_swingup'); addpath('C:/Capstone1/matlab_furuta/swingup_ppo/pi_wrappers');
cd(modelDir); load_system([modelName '.slx']); m=modelName;
cfg=getActiveConfigSet(m);
fprintf('RUN %s | board %s | addr %s | CAN %s\n',m,get_param(m,'HardwareBoard'),string(codertarget.data.getParameterValue(cfg,'BoardParameters.DeviceAddress')),string(codertarget.data.getParameterValue(cfg,'CAN.BusSpeed0')));
w=get_param(m,'ModelWorkspace'); fprintf('drive=%s limits=%s\n',mat2str(getVariable(w,'drive')),mat2str(getVariable(w,'limits')));
set_param(m,'SimulationMode','external','GenCodeOnly','off','StopTime','inf');
t0=tic; slbuild(m); fprintf('BUILD+DEPLOY done %.0f s\n',toc(t0));
set_param(m,'SimulationCommand','connect'); pause(2);
set_param(m,'SimulationCommand','start'); fprintf('STARTED %s\n',datestr(now,'HH:MM:SS'));
pause(runSeconds);
set_param(m,'SimulationCommand','stop'); pause(3);
try, set_param(m,'SimulationCommand','disconnect'); catch, end
fprintf('STOPPED %s\n',datestr(now,'HH:MM:SS'));
vars=evalin('base','who'); disp(vars');
if any(strcmp(vars,'logsout')), L=evalin('base','logsout');
elseif any(strcmp(vars,'out')), o=evalin('base','out'); L=o.logsout; else, L=[]; end
outDir='C:/Capstone1/runs_pid'; save(fullfile(outDir,[runTag '.mat']),'L');
if ~isempty(L), try, save_furuta_pi_telemetry(L,fullfile(outDir,[runTag '.jsonl'])); catch e, disp(e.message); end, end
fprintf('SAVED %s\n',runTag);
close_system(m,0);
