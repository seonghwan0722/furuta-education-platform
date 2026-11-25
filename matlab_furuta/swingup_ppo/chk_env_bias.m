addpath('C:/Capstone1/matlab_furuta'); addpath('C:/Capstone1/matlab_furuta/swingup_ppo'); addpath('C:/Capstone1/matlab_furuta/rev11');
c=rev11_ident_config(); ck=load('C:/Capstone1/matlab_furuta/results/ppo_swingup_20261119/run9_rev11_regen/ck_0380.mat','actor');
x0=[zeros(1,3); deg2rad([180 175 -175]); zeros(2,3)];
M=sp_eval2(ck.actor,x0,20,c,struct('filter',true,'delay',1,'armLim',15,'pendLim',25,'frac',0,'regenBudget',0.8)); fprintf('CHK nobias pass %d/3 reach %s\n',nnz(M.Passed),mat2str(round(M.ReachTime'*100)/100));
dr=struct('filter',true,'delayMax',1,'fracMax',1.0,'alpha',0.15,'coul',0.25,'eta',0.3,'regenBudget',0.8,'biasDeg',3,'coulThMax',1e-3);
s=sp_env2.reset(repmat([0;pi;0;0],1,6),c,dr); fprintf('CHK bias deg %s coulTh %s\n',mat2str(round(rad2deg(s.bias)*100)/100),mat2str(s.coulTh,2));
[o,s]=sp_env2.observe(s,c.Ts); s=sp_env2.step(s,zeros(1,6),c); s=sp_env2.resetSome(s,logical([1 0 1 0 0 0]),repmat([0;pi;0;0],1,2),dr,c); [o,s]=sp_env2.observe(s,c.Ts);
fprintf('CHK obs pend after reset %s (rates %s)\n',mat2str(round(rad2deg(atan2(o(2,:),o(1,:)))*100)/100),mat2str(round(o(5,:)*100)/100));
