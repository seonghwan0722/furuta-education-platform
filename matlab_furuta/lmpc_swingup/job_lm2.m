here='C:/Capstone1/matlab_furuta/lmpc_swingup'; addpath(here); addpath('C:/Capstone1/matlab_furuta'); addpath('C:/Capstone1/matlab_furuta/swingup_ppo');
out='C:/Capstone1/matlab_furuta/results/lmpc_swingup_20261120/';
g=struct('kE',400,'Erest',0.001,'v1',10,'v2',14,'capAng',deg2rad(20),'capRate',3,'relAng',deg2rad(40),'armClamp',0.6);
if ~exist('vmaxSet','var'), vmaxSet=13.5; end
D=lm_design(qObs=[200 800],fc=0,vmax=vmaxSet);
st=deg2rad([180 175 -175]); xf=[zeros(1,3); st; zeros(2,3)]; xr=[];
for sd=[2001 2002 2003], rng(sd,'twister'); xr=[xr [pi*(2*rand(1,40)-1); pi+deg2rad(30)*(2*rand(1,40)-1); 0.5*(2*rand(1,40)-1); 1*(2*rand(1,40)-1)]]; end %#ok<AGROW>
x0=[xf xr];
conds=[1 1 0; 1 1 0.5; 1 1 1.0; 0 1 0]; rows={};
for q=1:size(conds,1)
    ev=struct('filter',logical(conds(q,1)),'delay',conds(q,2),'armLim',15,'pendLim',25,'frac',conds(q,3));
    M=lm_eval(D,g,x0,25,ev); P=M.Passed;
    rows(end+1,:)={conds(q,1),10*(1+conds(q,3)),nnz(P(1:3)),nnz(P(4:end)),mean(M.ReachTime(P)),max(M.ReachTime(P)), ...
        mean(M.HoldMeanErrDeg(P)),max(M.HoldMaxErrDeg(P)),max(M.HoldMaxPendRate(P)),max(M.PeakCurrentA),max(M.PeakArmRate(P)),max(M.PeakPendRate(P))}; %#ok<SAGROW>
    F=M(~P,:); fprintf('cond %s failures: %s\n',mat2str(conds(q,:)),mat2str([F.StartDeg F.FirstLimitViolationT]',3));
end
T=cell2table(rows,'VariableNames',{'Filter30ms','DelayMs','Fixed3','Rand120','MeanReach','MaxReach','MeanHoldErr','MaxHoldErr','MaxHoldRate','MaxCurrent','MaxArmRate','MaxPendRate'});
disp(T); writetable(T,[out sprintf('stage1_batch_eval_vmax%g.csv',vmaxSet)]); save([out sprintf('stage1_design_vmax%g.mat',vmaxSet)],'D','g');
% robustness to plant mismatch (identified-candidate alpha/eta_phi from the other thread; NOT confirmed values)
for pl=[0.05 0.63 1e-4; 0.0244 0.63 0.092; 0.05 0.40 1e-4; 0.05 0.85 1e-4]'
    M=lm_eval(D,g,x0(:,1:43),25,struct('filter',true,'delay',1,'armLim',15,'pendLim',25,'frac',0,'plant',pl'));
    fprintf('plant alpha %.4f coul %.2f eta %.4g: %d/43\n',pl,nnz(M.Passed));
end
