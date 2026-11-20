root='C:/Capstone1/matlab_furuta'; addpath(root); addpath([root '/swingup_ppo']); addpath([root '/lmpc_swingup']); addpath([root '/rev11']);
load([root '/results/lmpc_swingup_20261120/pid_lqr_design_final.mat'],'g0');
cp=rev11_ident_config();
xr=[]; for sd=[2001 2002], rng(sd,'twister'); xr=[xr [pi*(2*rand(1,20)-1); pi+deg2rad(30)*(2*rand(1,20)-1); 0.5*(2*rand(1,20)-1); 1*(2*rand(1,20)-1)]]; end
x0=[[zeros(1,3); deg2rad([180 175 -175]); zeros(2,3)] xr];
ev=struct('filter',true,'delay',1,'armLim',15,'pendLim',25,'frac',0,'plantCfg',cp);
rows={};
for Q=[10 10 1 1; 10 10 0.3 0.3; 3 10 0.3 0.3]'
 for kE=[150 300 600]
  for capR=[3 4.5 6]
   D=lm_design(qObs=[200 800],fc=0,vmax=13.5,plantCfg=cp,Q=Q');
   g=g0; g.kE=kE; g.capRate=capR; g.brakeMax=0; g.brakeV=1; g.brakeMaxBal=0.33; g.brakeVBal=4;
   for mode=["lqr","lmpc"]
     g.balance=mode; [M,R]=lm_eval(D,g,x0,20,ev); P=M.Passed;
     A=R.A*cp.p.tau_max; V=squeeze(R.X(3,:,1:end-1)); Pr=max(0,-A.*V)*cp.Ts; e=0; em=0; for j=1:size(Pr,1), e=0; for k=1:size(Pr,2), if Pr(j,k)>0, e=e+Pr(j,k); em=max(em,e); else, e=0; end, end, end
     rows(end+1,:)={mode,mat2str(Q'),kE,capR,nnz(P(1:3)),nnz(P(4:end)),mean(M.ReachTime(P)),em}; %#ok<SAGROW>
     fprintf('%s Q=%s kE %d capR %.1f: fixed %d/3 rand %d/40 reach %.2f regenE %.2f J\n',mode,mat2str(Q'),kE,capR,nnz(P(1:3)),nnz(P(4:end)),mean(M.ReachTime(P)),em);
   end
  end
 end
end
T=cell2table(rows,'VariableNames',{'Mode','Q','kE','capRate','Fixed3','Rand40','MeanReach','MaxRegenJ'}); writetable(T,[root '/rev11/redesign_scan.csv']);
