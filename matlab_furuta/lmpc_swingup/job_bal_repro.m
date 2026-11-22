root='C:/Capstone1/matlab_furuta'; addpath(root); addpath([root '/lmpc_swingup']); addpath([root '/swingup_ppo']); addpath([root '/rev11']);
cp=rev11_ident_config(); L=load([root '/rev11/rev11_design.mat']); D=L.D; g=L.g;
x0=repmat([0; deg2rad(2); 0; 0],1,1);
for cond=1:4
  ev=struct('filter',true,'delay',1,'armLim',15,'pendLim',25,'frac',0,'plantCfg',cp);
  switch cond, case 2, ev.stic=0.5; case 3, ev.stic=0.5; ev.biasDeg=1; case 4, ev.stic=0.5; ev.biasDeg=1; ev.coulTh=1e-3; end
  [~,R]=lm_eval(D,g,x0,20,ev); S=bal_metric(R,4);
  fprintf('REPRO LMPC cond %d: longest %.2f s, |w|>0.5 frac %.3f, std th %.2f deg, u flips/s %.1f, max th %.2f\n',cond,S);
end
