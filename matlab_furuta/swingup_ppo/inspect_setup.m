function inspect_setup
root=fileparts(fileparts(mfilename('fullpath')));
addpath(root);
c1=fullfile(root,'results','ppo_rmd_candidate_tpa79dc374_f9fe_4d66_a12a_2e210f4a8415','ppo_013deg.mat');
c2=fullfile(root,'results','ppo_rmd_candidate_tp97fc9a76_8081_45c8_bc7c_d0c53084f14f','ppo_013deg.mat');
c3=fullfile(root,'results','ppo_rmd_candidate_tp97fc9a76_8081_45c8_bc7c_d0c53084f14f','ppo_005deg.mat');
for c={c1,c2,c3}
  w=whos('-file',c{1}); fprintf('%s\n vars: %s\n',c{1},strjoin({w.name},','));
  d=load(c{1},'p','opts','ampsPerAction','armLimit');
  disp(d.p); disp(d.opts); fprintf('amps/action %g armLimit %g\n',d.ampsPerAction,d.armLimit);
  try a=load(c{1},'actuation'); disp(a.actuation); end
end
m='furuta_rl_training'; load_system(fullfile(root,[m '.slx']));
w=get_param(m,'ModelWorkspace');
names={'plantCoefficients','maxTorque','rmdCommandDelaySamples','useRmd','controlPeriod','rmdCurrentTimeConstant','rlRewardLevel','controllerMode','lqrGain'};
for n=names, try v=getVariable(w,n{1}); fprintf('%s = %s\n',n{1},mat2str(v,6)); catch, fprintf('%s missing\n',n{1}); end, end
disp(getVariable(w,'rmd'));
fprintf('StopTime %s solver %s fixedstep %s\n',get_param(m,'StopTime'),get_param(m,'Solver'),get_param(m,'FixedStep'));
r=sfroot; ch=r.find('-isa','Stateflow.EMChart','Path',[m '/03 Controllers/RL observation reward termination']); disp(ch.Script);
blocks=find_system(m,'LookUnderMasks','all','FollowLinks','on','BlockType','ToWorkspace'); disp(blocks);
fprintf('dirty %s\n',get_param(m,'Dirty'));
close_system(m,0);
f='furuta_block_model_fixed'; load_system(fullfile(root,[f '.slx'])); wf=get_param(f,'ModelWorkspace');
vs=wf.whos; for k=1:numel(vs), try v=getVariable(wf,vs(k).name); if isnumeric(v)&&numel(v)<=20, fprintf('FIXED %s = %s\n',vs(k).name,mat2str(v,6)); elseif isstruct(v), fprintf('FIXED %s struct: %s\n',vs(k).name,strjoin(fieldnames(v)',',')); end; end; end
close_system(f,0);
end
