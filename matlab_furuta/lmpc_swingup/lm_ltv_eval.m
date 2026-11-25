function [M,R,tStep] = lm_ltv_eval(D,P,x0,T,ev)
% Single-env rollouts of the stage-2 LTV-MPC in sp_env2 (Pi observation path).
c=D.c; n=size(x0,2); N=round(T/c.Ts);
dr=struct('filter',ev.filter,'delayMax',1,'alpha',0,'coul',0,'eta',0);
c2=c; c2.delaySteps=ev.delay;
X=zeros(4,n,N+1); X(:,:,1)=x0; A=zeros(n,N); U=zeros(n,N); tt=0; cnt=0;
for j=1:n
    s=sp_env2.reset(x0(:,j),c2,dr); s.delay(:)=ev.delay;
    if isfield(ev,'frac'), s.frac(:)=ev.frac; end
    mem=struct();
    for k=1:N
        [o,s]=sp_env2.observe(s,c.Ts);
        t0=tic; if isfield(P,"ctrl"), [u,mem]=P.ctrl(o,mem,D,P); else, [u,mem]=lm_ltv_controller(o,mem,D,P); end; tt=tt+toc(t0); cnt=cnt+1;
        [s,ap]=sp_env2.step(s,u,c2);
        X(:,j,k+1)=s.x; A(j,k)=ap; U(j,k)=u;
        if abs(s.x(3))>=ev.armLim || abs(s.x(4))>=ev.pendLim, X(:,j,k+2:end)=repmat(s.x,1,N-k); break; end
    end
end
R.X=X; R.A=A; R.U=U; R.t=(0:N)*c.Ts; tStep=tt/cnt;
M=sp_metrics(R,c,ev.armLim,ev.pendLim);
end
