base='C:/Capstone1/matlab_furuta/results/ppo_swingup_20261119/';
if ~exist('ckName','var'), ckName='sac15_lit/ck_0100.mat'; end
ck=load([base ckName]); agent=sp_export_agent(ck);
out=strrep(strrep(ckName,'/','_'),'.mat','');
save([base 'candidate_' out '_agent.mat'],'agent');
xr=[[zeros(1,3); deg2rad([180 175 -175]); zeros(2,3)]];
for sd=[3001 3002], rng(sd,'twister'); n=5; xr=[xr [pi*(2*rand(1,n)-1); pi+deg2rad(30)*(2*rand(1,n)-1); 0.5*(2*rand(1,n)-1); 1*(2*rand(1,n)-1)]]; end %#ok<AGROW>
if exist('nStarts','var'), xr=xr(:,1:nStarts); end
[M,tr]=sp_fixed_eval(agent,xr,25,MilLimits=[15 25]);
writetable(M,[base 'fixed_mil_' out '.csv']); save([base 'fixed_mil_' out '.mat'],'M','tr','xr');
fprintf('FIXED SUMMARY %s: %d/%d\n',ckName,nnz(M.Passed),height(M));
