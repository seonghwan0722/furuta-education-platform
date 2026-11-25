here='C:/Capstone1/matlab_furuta/lmpc_swingup'; addpath(here); addpath('C:/Capstone1/matlab_furuta'); addpath('C:/Capstone1/matlab_furuta/swingup_ppo');
load('C:/Capstone1/matlab_furuta/results/lmpc_swingup_20261120/stage1_design.mat','D','g');
xr=[]; for sd=[2001 2002 2003], rng(sd,'twister'); xr=[xr [pi*(2*rand(1,40)-1); pi+deg2rad(30)*(2*rand(1,40)-1); 0.5*(2*rand(1,40)-1); 1*(2*rand(1,40)-1)]]; end
[M,R]=lm_eval(D,g,xr,3,struct('filter',true,'delay',1,'armLim',15,'pendLim',25,'frac',0));
F=find(~M.Passed); 
for j=F(:)'
  v=squeeze(R.X(3,j,:)); w=squeeze(R.X(4,j,:)); th=rad2deg(atan2(sin(squeeze(R.X(2,j,:))),cos(squeeze(R.X(2,j,:))))); k=find(abs(v)>=15|abs(w)>=25,1);
  if isempty(k), fprintf('start %.0f no violation in 3s\n',M.StartDeg(j)); continue; end
  fprintf('start %.0f: viol t=%.2f v=%.1f w=%.1f th=%.1f | u(k-5..k)=%s\n',M.StartDeg(j),R.t(k),v(k),w(k),th(k),mat2str(R.U(j,max(1,k-6):k-1),2));
end
