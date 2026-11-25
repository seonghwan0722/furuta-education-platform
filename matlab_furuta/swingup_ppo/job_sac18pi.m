root='C:/Capstone1/matlab_furuta'; addpath(root); addpath([root '/swingup_ppo']); addpath([root '/swingup_ppo/pi_wrappers']); rehash;
c=sp_config; dr=struct('filter',true,'delayMax',1,'alpha',0,'coul',0,'eta',0);
for nm=["furuta_sac_full_step","furuta_sac_bal_step"]
  fn=str2func(nm); st=[pi deg2rad(6)];
  for j=1:2
    clear(char(nm)); s=sp_env2.reset([0;st(j);0;0],c,dr); X=zeros(4,1,2001); X(:,1,1)=[0;st(j);0;0]; A=zeros(1,2000);
    for k=1:2000, [o,s]=sp_env2.observe(s,c.Ts); u=fn([o(3);atan2(o(2),o(1));o(4);o(5)],true); [s,ap]=sp_env2.step(s,u,c); X(:,1,k+1)=s.x; A(k)=ap; end
    R.X=X;R.A=A;R.t=(0:2000)*c.Ts; M=sp_metrics(R,c,15,25);
    fprintf('WRAPCHK %s start %.0f pass %d\n',nm,rad2deg(st(j)),M.Passed);
  end
end
out=[root '/results/ppo_swingup_20261119/pi_models_wrapped']; extraPath=[root '/swingup_ppo/pi_wrappers'];
ctrls={'furuta_sac_bal_step','furuta_sac_full_step'};
run([root '/lmpc_swingup/job_pi_classical.m']);
