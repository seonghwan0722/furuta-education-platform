% Export MATLAB PPO/SAC actor weights + plant params for the Python MuJoCo cross-check, and run the
% MATLAB reference evaluation (sp_eval2, 16 fixed starts, 25 s) under the same plant variants.
% Read-only on all existing results; writes only to mujoco_crosscheck/matlab_export.
addpath('C:/Capstone1/matlab_furuta'); addpath('C:/Capstone1/matlab_furuta/swingup_ppo'); addpath('C:/Capstone1/matlab_furuta/rev11');
base='C:/Capstone1/matlab_furuta/results/ppo_swingup_20261119/'; out='C:/Capstone1/mujoco_crosscheck/matlab_export/';
cks={'run9_rev11_regen/ck_0380','run10_rev11_bias/ck_0250','run12_rev11_hold_lo/ck_0300','run13_rev11_delay/ck_0300', ...
     'sac19_rev11_regen/ck_0100','sac22_rev11_stic2x/ck_0150','sac22_rev11_stic2x/ck_0400', ...
     'sac24_rev11_armrate2/ck_0100','sac24_rev11_armrate2/ck_0200','sac25_v3_opt/ck_0150','sac25_v3_opt/ck_0200'};
c0=rev11_ident_config(); cc=rev11_config("with_tip");
P=struct('ident',c0.p,'cad',cc.p,'Kt',c0.Kt,'maxCurrent',c0.maxCurrent,'currentLSB',c0.currentLSB,'Ts',c0.Ts,'sc',sp_scale);
save([out 'plant_params.mat'],'-struct','P','-v7');
evalStarts=deg2rad([180 175 -175 177 -172 168 -165 160 -156 150 -145 13 -13 8 -4 0]);
xe=[zeros(1,16); evalStarts; zeros(2,16)];
% condition: name, delay, frac, coulomb scale, eta_phi scale, alpha scale, override [alpha coul eta] (NaN = none)
conds={'nom10',1,0,1,1,1,[NaN NaN NaN]; 'd20',1,1,1,1,1,[NaN NaN NaN]; 'fric075',1,0,0.75,0.75,1,[NaN NaN NaN]; ...
       'fric125',1,0,1.25,1.25,1,[NaN NaN NaN]; 'inert085',1,0,1,1,0.85,[NaN NaN NaN]; 'inert115',1,0,1,1,1.15,[NaN NaN NaN]; ...
       'hw1123',1,0,1,1,1,[0.0250+2.358e-4 0.785 0.186]; 'd20_fric125',1,1,1.25,1.25,1,[NaN NaN NaN]};
rows={};
for i=1:numel(cks)
  ck=load([base cks{i} '.mat']);
  L=ck.actor.Learnables; W=struct();
  for k=1:height(L), W.([char(L.Layer(k)) '_' char(L.Parameter(k))])=double(extractdata(L.Value{k})); end
  W.stored_d1=double(ck.eval.Passed'); W.stored_d2=double(ck.evalD2.Passed');
  W.name=cks{i}; save([out strrep(cks{i},'/','__') '.mat'],'-struct','W','-v7');
  for q=1:size(conds,1)
    c=c0; c.p.coulomb=c.p.coulomb*conds{q,4}; c.p.eta_phi=c.p.eta_phi*conds{q,5}; c.p.alpha=c.p.alpha*conds{q,6};
    ov=conds{q,7}; if ~isnan(ov(1)), c.p.alpha=ov(1); c.p.coulomb=ov(2); c.p.eta_phi=ov(3); end
    t0=tic; M=sp_eval2(ck.actor,xe,25,c,struct('filter',true,'delay',conds{q,2},'armLim',15,'pendLim',25,'frac',conds{q,3},'regenBudget',0.8));
    rows(end+1,:)={cks{i},conds{q,1},nnz(M.Passed),mat2str(double(M.Passed')),mean(M.ReachTime(M.Passed)),max(M.HoldMaxErrDeg(M.Passed)),max(M.PeakArmRate),toc(t0)}; %#ok<SAGROW>
    fprintf('%s %s pass %d/16 (%.1fs)\n',cks{i},conds{q,1},nnz(M.Passed),toc(t0));
  end
end
T=cell2table(rows,'VariableNames',{'Checkpoint','Cond','Pass','PassVec','MeanReach','MaxHoldErr','MaxArmRate','EvalSec'});
writetable(T,[out 'matlab_eval.csv']); disp(T)
