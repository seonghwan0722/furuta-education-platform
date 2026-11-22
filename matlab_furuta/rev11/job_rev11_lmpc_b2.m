root='C:/Capstone1/matlab_furuta'; here=[root '/lmpc_swingup']; addpath(root); addpath([root '/swingup_ppo']); addpath(here); addpath([root '/rev11']);
L=load([root '/rev11/rev11_design.mat']); B=load([root '/rev11/rev11_design_b.mat']); cp=B.cp; g=B.g;
x0=[zeros(1,3); deg2rad([180 175 -175]); zeros(2,3)];
for cond=1:4
  ev=struct('filter',true,'delay',1,'armLim',15,'pendLim',25,'frac',0,'plantCfg',cp,'stic',0.5,'coulTh',1e-3);
  switch cond, case 1, ev.biasDeg=-1; case 2, ev.biasDeg=-1; ev.coulTh=0; case 3, ev.biasDeg=0; ev.frac=1; case 4, ev.biasDeg=-1; ev.stic=0; ev.coulTh=0; end
  for DD={L.D,B.D}
    gg=g; gg.balance="lmpc"; [M,R]=lm_eval(DD{1},gg,x0,20,ev); S=bal_metric(R,4);
    fprintf('B2 cond %d Q=%s: pass %d/3 longest %s std th %s\n',cond,mat2str(DD{1}.opts.Q),nnz(M.Passed),mat2str(round(S(:,1)'*10)/10),mat2str(round(S(:,3)'*100)/100));
  end
end
