% Training stability / time metrics for every PPO and SAC run folder (from train_log.csv, config.mat, checkpoint times).
base='C:/Capstone1/matlab_furuta/results/ppo_swingup_20261119/';
D=dir(base); D=D([D.isdir]); names={D.name}; names=names(startsWith(names,'run')|startsWith(names,'sac'));
R=table();
for i=1:numel(names)
  f=[base names{i} '/']; if ~isfile([f 'train_log.csv']), continue; end
  T=readtable([f 'train_log.csv']); C=load([f 'config.mat']); cfg=C.cfg;
  ck=dir([f 'ck_*.mat']); if numel(ck)<2, continue; end
  [~,o]=sort([ck.datenum]); ck=ck(o); it=cellfun(@(s) sscanf(s,'ck_%d.mat'),{ck.name});
  secPerIt=(ck(end).datenum-ck(1).datenum)*86400/(it(end)-it(1));
  isSac=startsWith(names{i},'sac');
  if isSac, stepsPerIt=cfg.nEnv*cfg.stepsPerIter; updPerIt=cfg.updatesPerIter; else, stepsPerIt=cfg.nEnv*cfg.horizon; updPerIt=NaN; end
  e=~isnan(T.EvalPass); ep=T.EvalPass(e); ed=T.EvalPassD2(e); n=16;
  late=ep(max(1,end-floor(numel(ep)/2)+1):end);              % second half of evaluations
  drops=max([0; -diff(ep)]);
  reg=nnz(diff(ep)<=-2);                                      % regressions of >=2 starts between evaluations
  first14=find(ep>=14,1); t14=NaN; if ~isempty(first14), ei=T.Iter(e); t14=ei(first14)*secPerIt/60; end
  r=T.MeanEpReturn(~isnan(T.MeanEpReturn)); rl=r(max(1,end-floor(numel(r)/2)+1):end);
  row=table(string(names{i}),string(ifelse(isSac,'SAC','PPO')),height(T),secPerIt,stepsPerIt,stepsPerIt/secPerIt,height(T)*secPerIt/60, ...
    mean(late)/n,std(late)/n,min(late)/n,drops/n,reg,t14,mean(ed(max(1,end-numel(late)+1):end))/n,std(rl)/max(eps,abs(mean(rl))), ...
    'VariableNames',{'Run','Algo','Iters','SecPerIter','EnvStepsPerIter','EnvStepsPerSec','WallMin','LateEvalMean','LateEvalStd','LateEvalMin','MaxDrop','Regressions','MinTo14of16','LateD2Mean','LateReturnCV'});
  R=[R; row]; %#ok<AGROW>
end
writetable(R,'C:/Capstone1/matlab_furuta/swingup_ppo/metrics/train_metrics.csv');
disp(R(:,[1 2 3 4 6 7 8 9 10 11 12 13 14 15]));
function y=ifelse(c,a,b), if c, y=a; else, y=b; end, end
