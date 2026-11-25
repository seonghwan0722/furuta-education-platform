function T = sp_cross(cks,seeds,nRand)
c=sp_config; base='C:/Capstone1/matlab_furuta/results/ppo_swingup_20261119/';
st=deg2rad([180 175 -175]); xf=[zeros(1,3); st; zeros(2,3)]; xr=[];
for sd=seeds, rng(sd,'twister'); xr=[xr [pi*(2*rand(1,nRand)-1); pi+deg2rad(30)*(2*rand(1,nRand)-1); 0.5*(2*rand(1,nRand)-1); 1*(2*rand(1,nRand)-1)]]; end %#ok<AGROW>
x0=[xf xr]; rows={}; mx=@(v) max([v(:); -Inf]);
for i=1:numel(cks)
  ck=load([base cks{i}],'actor');
  conds=[0 1 0; 1 1 0; 1 1 0.5; 1 1 1.0; 0 2 0];
  for q=1:size(conds,1)
   filt=logical(conds(q,1)); d=conds(q,2);
    M=sp_eval2(ck.actor,x0,25,c,struct('filter',filt,'delay',d,'armLim',15,'pendLim',25,'frac',conds(q,3))); P=M.Passed; rr=M(P,:);
    rows(end+1,:)={cks{i},filt,d+conds(q,3),nnz(P(1:3)),nnz(P(4:end)),numel(P)-3,mean(rr.ReachTime),mx(rr.ReachTime),mx(rr.HoldMaxErrDeg),mx(rr.HoldMaxPendRate)}; %#ok<AGROW>
  end
end
T=cell2table(rows,'VariableNames',{'Checkpoint','Filter30ms','DelaySteps','FixedPass3','RandPass','RandN','MeanReach','MaxReach','MaxHoldErr','MaxHoldRate'}); disp(T)
end
