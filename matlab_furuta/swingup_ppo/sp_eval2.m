function [M,R] = sp_eval2(actor,x0,T,c,ev)
% Deterministic policy rollout in sp_env2. ev: struct(filter,delay,armLim,pendLim)
sc=single(sp_scale); n=size(x0,2); N=round(T/c.Ts);
dr=struct('filter',ev.filter,'delayMax',1,'alpha',0,'coul',0,'eta',0);
if isfield(ev,'regenBudget'), dr.regenBudget=ev.regenBudget; end
c2=c; c2.delaySteps=ev.delay;
s=sp_env2.reset(x0,c2,dr); s.delay(:)=ev.delay;
if isfield(ev,'frac'), s.frac(:)=ev.frac; end
X=zeros(4,n,N+1); X(:,:,1)=x0; A=zeros(n,N); U=zeros(n,N);
for k=1:N
    [o,s]=sp_env2.observe(s,c.Ts);
    u=double(extractdata(predict(actor,dlarray(single(o)./sc,'CB'))));
    [s,ap]=sp_env2.step(s,u,c2);
    X(:,:,k+1)=s.x; A(:,k)=ap; U(:,k)=u;
end
R.X=X; R.A=A; R.U=U; R.t=(0:N)*c.Ts;
M=sp_metrics(R,c,ev.armLim,ev.pendLim);
end
