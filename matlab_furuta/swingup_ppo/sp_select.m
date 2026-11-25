function T = sp_select(run,filter,iters,seeds,nRand)
% Evaluate checkpoints on fixed starts + random hanging starts (unseen seeds). Baseline plant.
c=sp_config; f=fullfile('C:/Capstone1/matlab_furuta/results/ppo_swingup_20261119',run);
st=deg2rad([180 175 -175]); xf=[zeros(1,3); st; zeros(2,3)];
xr=[];
for sd=seeds
    rng(sd,'twister');
    xr=[xr [pi*(2*rand(1,nRand)-1); pi+deg2rad(30)*(2*rand(1,nRand)-1); 0.5*(2*rand(1,nRand)-1); 1*(2*rand(1,nRand)-1)]]; %#ok<AGROW>
end
x0=[xf xr]; rows=[]; mx=@(v) max([v(:); -Inf]);
for it=iters
    ck=load(fullfile(f,sprintf('ck_%04d.mat',it)),'actor');
    for d=1:2
        M=sp_eval2(ck.actor,x0,25,c,struct('filter',filter,'delay',d,'armLim',15,'pendLim',25));
        P=M.Passed; rr=M(P,:);
        rows(end+1,:)=[it d nnz(P(1:3)) nnz(P(4:end)) numel(P)-3 mean(rr.ReachTime) mx(rr.ReachTime) mean(rr.HoldMeanErrDeg) mx(rr.HoldMaxErrDeg) max(M.PeakArmRate) max(M.PeakPendRate) max(M.PeakCurrentA)]; %#ok<AGROW>
    end
end
T=array2table(rows,'VariableNames',{'Iter','Delay','FixedPass3','RandPass','RandN','MeanReach','MaxReach','MeanHoldErr','MaxHoldErr','MaxArm','MaxPend','MaxCurrent'});
disp(T); writetable(T,fullfile(f,sprintf('selection_%s.csv',strjoin(string(seeds),'_'))));
end
