addpath('C:/Capstone1/matlab_furuta/rev11'); base='C:/Capstone1/matlab_furuta/results/ppo_swingup_20261119/';
c=rev11_ident_config(); st=deg2rad([180 175 -175]); xf=[zeros(1,3); st; zeros(2,3)]; xr=[];
for sd=[2001 2002], rng(sd,'twister'); xr=[xr [pi*(2*rand(1,40)-1); pi+deg2rad(30)*(2*rand(1,40)-1); 0.5*(2*rand(1,40)-1); 1*(2*rand(1,40)-1)]]; end
x0=[xf xr];
if ~exist('cks','var'), cks={'run7_margin/ck_0250.mat','run9_rev11_regen/ck_0300.mat','run9_rev11_regen/ck_0350.mat','run9_rev11_regen/ck_0380.mat','run9_rev11_regen/ck_0400.mat'}; end
for i=1:numel(cks)
  ck=load([base cks{i}],'actor');
  for fr=[0 0.5]
    M=sp_eval2(ck.actor,x0,20,c,struct('filter',true,'delay',1,'armLim',15,'pendLim',25,'frac',fr,'regenBudget',0.8));
    P=M.Passed; fprintf('RL %-32s delay %2.0f ms: fixed %d/3 rand %d/80 meanReach %.2f maxArm %.1f\n',cks{i},10*(1+fr),nnz(P(1:3)),nnz(P(4:end)),mean(M.ReachTime(P)),max(M.PeakArmRate(P)));
  end
end
