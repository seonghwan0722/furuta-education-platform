function [M,R] = sp_eval_hist(actor,x0,T,c,ev)
% Deterministic rollout for the 8-input history actor:
% obs = [Pi obs (scaled 5); previous scaled filtered rates (2); last commanded action (1)].
sc=single(sp_scale); n=size(x0,2); N=round(T/c.Ts);
dr=struct('filter',ev.filter,'delayMax',1,'alpha',0,'coul',0,'eta',0);
c2=c; c2.delaySteps=ev.delay;
s=sp_env2.reset(x0,c2,dr); s.delay(:)=ev.delay;
if isfield(ev,'frac'), s.frac(:)=ev.frac; end
X=zeros(4,n,N+1); X(:,:,1)=x0; A=zeros(n,N); U=zeros(n,N);
prevRates=[];
for k=1:N
    [o,s]=sp_env2.observe(s,c.Ts); o=single(o)./sc;
    if isempty(prevRates), prevRates=o(4:5,:); end
    oh=[o; prevRates; single(s.queue(1,:))];
    u=double(extractdata(predict(actor,dlarray(oh,'CB'))));
    [s,ap]=sp_env2.step(s,u,c2);
    prevRates=o(4:5,:);
    X(:,:,k+1)=s.x; A(:,k)=ap; U(:,k)=u;
end
R.X=X; R.A=A; R.U=U; R.t=(0:N)*c.Ts;
M=sp_metrics(R,c,ev.armLim,ev.pendLim);
end
