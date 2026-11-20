addpath('C:/Capstone1/matlab_furuta/lmpc_swingup'); addpath('C:/Capstone1/matlab_furuta');
root='C:/Capstone1/matlab_furuta'; if ~exist('out','var'), out=[root '/results/lmpc_swingup_20261120/pi_models']; end
if exist('extraPath','var'), addpath(extraPath); end
if ~exist('ctrls','var'), ctrls=["furuta_lqr_step","furuta_pid_step","furuta_lmpc_step"]; end
for cf=string(ctrls)
  sub=fullfile(out,char(cf)); if ~isfolder(sub), mkdir(sub); end
  old=cd(sub);
  for armed=[false true]
    if armed
      f=build_furuta_pi_hardware(ControllerFunction=cf,Folder=sub,DriveProfile=fullfile(root,'..','deployment','pi','rmd_speed_drive_candidate.json'));
    else
      f=build_furuta_pi_hardware(ControllerFunction=cf,Folder=sub);
    end
    load_system(f); [~,m]=fileparts(f); w=get_param(m,'ModelWorkspace');
    fprintf('%s %s drive=%s limits=%s\n',cf,m,mat2str(getVariable(w,'drive')),mat2str(getVariable(w,'limits')));
    set_param(m,'GenCodeOnly','on','RTWVerbose','off'); slbuild(m); close_system(m,0);
    fprintf('CODEGEN OK %s %s\n',cf,m);
  end
  cd(old);
end
