function sp_codegen_check(agentFile,outDir)
% Generate C source (no compile) for the greedy PPO policy to check codegen compatibility.
d=load(agentFile); cd(outDir);
fprintf('Coder license: %d\n',license('test','MATLAB_Coder'));
generatePolicyFunction(d.agent,'MATFileName','candidatePolicyData.mat','FunctionName','evaluateCandidatePolicy');
cfg=coder.config('lib'); cfg.GenCodeOnly=true; cfg.TargetLang='C';
cfg.DeepLearningConfig=coder.DeepLearningConfig('none');
codegen('-config',cfg,'evaluateCandidatePolicy','-args',{ones(5,1)},'-report','-d','cg');
% numeric check of generated MATLAB policy vs agent
o=[cos(2.5);sin(2.5);-1.2;3.0;-4.0]; a1=evaluateCandidatePolicy(o); a2=getAction(getGreedyPolicy(d.agent),{o});
fprintf('POLICY FUNCTION %.6f vs AGENT %.6f\n',a1,a2{1});
fprintf('CODEGEN_DONE files: %d\n',numel(dir(fullfile('cg','*.c'))));
end
