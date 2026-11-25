function [M,R] = sp_policy_eval(actor,x0,T,c,armLim)
% Deterministic (mean) policy rollout in the batched env.
sc=sp_scale;
pol=@(o,x,m) deal(double(extractdata(predict(actor,dlarray(single(o./sc),'CB')))),m);
R=sp_rollout(pol,x0,T,c);
if nargin<5, armLim=c.armRateLimitTrain; end
M=sp_metrics(R,c,armLim,c.pendRateLimitPC);
end
