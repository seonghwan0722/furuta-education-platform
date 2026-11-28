% Export rev22 PPO/SAC actors to JSON (Python rl_eval / MatlabPolicyNP) and run the MATLAB-side lightweight batch
% (3 fixed + 120 random starts, seeds 2001-2003, sp_eval2, regen budget 0.8, delay 10/15/20 ms) on rev22_hw_config.
% Set variable cks (cell of 'subdir/ck_XXXX') before running.
root='C:/Capstone1/matlab_furuta'; addpath(root); addpath([root '/swingup_ppo']); addpath([root '/rev11']); addpath([root '/rev22']);
base=[root '/results/rev22_rl_20261127/']; out=[base 'export/']; if ~isfolder(out), mkdir(out); end
c=rev22_hw_config();
xr=[]; for sd=[2001 2002 2003], rng(sd,'twister'); xr=[xr [pi*(2*rand(1,40)-1); pi+deg2rad(30)*(2*rand(1,40)-1); 0.5*(2*rand(1,40)-1); 1*(2*rand(1,40)-1)]]; end
x0=[[zeros(1,3); deg2rad([180 175 -175]); zeros(2,3)] xr];
rows={};
for i=1:numel(cks)
  ck=load([base cks{i} '.mat']); L=ck.actor.Learnables; W=struct();
  for k=1:height(L), W.([char(L.Layer(k)) '_' char(L.Parameter(k))])=double(extractdata(L.Value{k})); end
  W.name=cks{i}; fid=fopen([out strrep(cks{i},'/','__') '.json'],'w'); fprintf(fid,'%s',jsonencode(W)); fclose(fid);
  for fr=[0 0.5 1]
    M=sp_eval2(ck.actor,x0,25,c,struct('filter',true,'delay',1,'armLim',15,'pendLim',25,'frac',fr,'regenBudget',0.8));
    rows(end+1,:)={cks{i},10+10*fr,nnz(M.Passed),mean(M.ReachTime(M.Passed)),max(M.PeakArmRate)}; %#ok<SAGROW>
    fprintf('MLEVAL %s %2d ms: %d/123 meanReach %.2f\n',cks{i},10+10*fr,nnz(M.Passed),mean(M.ReachTime(M.Passed)));
  end
end
T=cell2table(rows,'VariableNames',{'Checkpoint','DelayMs','Pass123','MeanReach','MaxArmRate'});
writetable(T,[out sprintf('matlab_eval123_%s.csv',datestr(now,'HHMMSS'))]); disp(T)
