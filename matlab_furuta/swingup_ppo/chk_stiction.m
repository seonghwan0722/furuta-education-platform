root='C:/Capstone1/matlab_furuta'; addpath(root); addpath([root '/swingup_ppo']); addpath([root '/rev11']); addpath([root '/swingup_ppo/pi_wrappers']);
c=rev11_ident_config();
for fn=["furuta_sac_rev11b_step","furuta_ppo_rev11b_step"]
 for sm=[0 0.3]
  dr=struct('filter',true,'delayMax',1,'fracMax',0,'alpha',0,'coul',0,'eta',0,'regenBudget',0.8);
  if sm>0, dr.stictionMax=1e-9; end
  th0=pi+deg2rad(-0.87); s=sp_env2.reset([0;th0;0;0],c,dr); if sm>0, s.coulS=c.p.coulomb*(1+sm); end
  f=str2func(fn); clear(char(fn)); mv=0; th=0;
  for k=1:2000, [o,s]=sp_env2.observe(s,c.Ts); u=f([o(3); atan2(o(2),o(1))+deg2rad(2.77); o(4); o(5)],true); s=sp_env2.step(s,u,c); mv=max(mv,abs(s.x(3))); th=atan2(sin(s.x(2)),cos(s.x(2))); end
  fprintf('STICK %s stiction +%.0f%%: max arm rate %.2f final |th| %.1f deg\n',fn,100*sm,mv,abs(rad2deg(th)));
 end
end
