root='C:/Capstone1/matlab_furuta'; addpath(root); addpath([root '/lmpc_swingup']); addpath([root '/swingup_ppo/pi_wrappers']); rehash;
if ~exist('out','var'), out=[root '/results/pi_drive20s']; end; if ~exist('profName','var'), profName='rmd_drive_20s.json'; end; prof=fullfile(root,'..','deployment','pi',profName);
if ~exist('missTol','var'), missTol=2; end
if ~exist("ctrls","var"), ctrls=["furuta_pid_bal_step","furuta_pid_step"]; end
for cf=string(ctrls)
  sub=fullfile(out,char(cf)); if ~isfolder(sub), mkdir(sub); end; old=cd(sub);
  f=build_furuta_pi_hardware(ControllerFunction=cf,Folder=sub,DriveProfile=prof,MissTolerance=missTol,TimingLog=exist('timingLog','var')&&timingLog);
  load_system(f); [~,m]=fileparts(f); w=get_param(m,'ModelWorkspace');
  dv=getVariable(w,'drive'); lv=getVariable(w,'limits');
  set_param(m,'GenCodeOnly','on','RTWVerbose','off'); slbuild(m); close_system(m,0);
  fprintf('DRIVE20 %s drive=%s limits=%s\n',cf,mat2str(dv),mat2str(lv));
  cd(old);
end
