root='C:/Capstone1/matlab_furuta'; addpath(root); addpath([root '/swingup_ppo']); addpath([root '/lmpc_swingup']); addpath([root '/rev11']);
load([root '/results/lmpc_swingup_20261120/pid_lqr_design_final.mat'],'D','g0');
cp=rev11_ident_config();
xr=[]; for sd=[2001 2002], rng(sd,'twister'); xr=[xr [pi*(2*rand(1,20)-1); pi+deg2rad(30)*(2*rand(1,20)-1); 0.5*(2*rand(1,20)-1); 1*(2*rand(1,20)-1)]]; end
x0=[[zeros(1,3); deg2rad([180 175 -175]); zeros(2,3)] xr];
ev=struct('filter',true,'delay',1,'armLim',15,'pendLim',25,'frac',0,'plantCfg',cp);
r7=struct('brakeMax',0,'brakeV',1,'brakeMaxBal',0.33,'brakeVBal',4,'capRate',4.5,'pidScale',0.75);
tests={'PID original',"pid",struct(); 'PID r7 (hardware OK)',"pid",r7; 'LQR original',"lqr",struct(); 'LQR + r7 guards',"lqr",rmfield(r7,'pidScale'); 'LMPC original',"lmpc",struct(); 'LMPC + r7 guards',"lmpc",rmfield(r7,'pidScale')};
for i=1:size(tests,1)
  g=g0; g.balance=tests{i,2}; f=fieldnames(tests{i,3}); for q=1:numel(f), g.(f{q})=tests{i,3}.(f{q}); end
  [M,R]=lm_eval(D,g,x0,20,ev); P=M.Passed;
  A=R.A*cp.p.tau_max; V=squeeze(R.X(3,:,1:end-1)); Pr=max(0,-A.*V)*cp.Ts; ev_=0; for j=1:size(Pr,1), e=0; for k=1:size(Pr,2), if Pr(j,k)>0, e=e+Pr(j,k); ev_=max(ev_,e); else, e=0; end, end, end
  fprintf('%-22s rev11id: fixed %d/3 rand %d/40 meanReach %.2f maxArm %.1f maxPend %.1f | max braking-event energy %.2f J\n',tests{i,1},nnz(P(1:3)),nnz(P(4:end)),mean(M.ReachTime(P)),max(M.PeakArmRate),max(M.PeakPendRate),ev_);
end
