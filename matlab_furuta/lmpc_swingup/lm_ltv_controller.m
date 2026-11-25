function [u,mem,info] = lm_ltv_controller(o,mem,D,P)
% Stage-2 controller: ONE linear-MPC QP per control step on a model re-linearized along the
% predicted trajectory (LTV-MPC / real-time iteration, Gauss-Newton cost). No separate swing-up law.
% o: Pi observation (5x1). D: lm_design struct (observer gain, plant). P: LTV-MPC settings.
c=D.c; p=c.p;
thm=atan2(o(2),o(1)); phm=o(3);
if ~isfield(mem,'xh')
    mem.xh=[phm;thm;0;0]; mem.c1=0; mem.c2=0;
    mem.U=P.U0(:);                                     % nominal block inputs
else
    xp=rk4(mem.xh,mem.c2,p,c.Ts);
    e=[wrap(phm-xp(1)); wrap(thm-xp(2))];
    mem.xh=xp+D.L*e;
end
xf=rk4(mem.xh,mem.c1,p,c.Ts);          % state when the new command starts acting
dts=P.dts(:); N=numel(dts); U=mem.U;
% nominal rollout + finite-difference sensitivities (state 4 + input 1 perturbations as columns)
X=zeros(4,N+1); X(:,1)=xf; A=zeros(4,4,N); B=zeros(4,N); ep=1e-5; pl=p; pl.coulomb=0;
for k=1:N
    Z=[X(:,k) X(:,k)+ep*eye(4) X(:,k)];
    a=[U(k)*ones(1,5) U(k)+ep];
    % nominal step keeps Coulomb friction; sensitivities use a friction-free copy
    % (sign(v) makes finite differences explode when the arm rate is near zero)
    X(:,k+1)=rk4(X(:,k),U(k),p,dts(k));
    Y=rk4(Z,a,pl,dts(k));
    A(:,:,k)=(Y(:,2:5)-Y(:,1))/ep; B(:,k)=(Y(:,6)-Y(:,1))/ep;
end
% condensed sensitivities dX_{k} / dU
S=zeros(4*N,N);
for k=1:N
    S((k-1)*4+(1:4),k)=B(:,k);
    for j=1:k-1
        S((k-1)*4+(1:4),j)=A(:,:,k)*S((k-2)*4+(1:4),j);
    end
end
% residuals per stage (state after block k): Gauss-Newton linearization
nr=4; R0=zeros(nr*N,1); Jx=zeros(nr*N,4*N);
for k=1:N
    x=X(:,k+1); th=x(2); w=x(4); v=x(3); wk=P.w; if k==N, wk=wk*P.terminal; end
    s=sqrt(dts(k)/0.05);                                   % weight by block length
    near=(1+cos(th))/2;
    r=s*[wk(1)*(1-cos(th)); wk(2)*sin(th); wk(3)*v; wk(4)*near*w];
    J=s*[0 wk(1)*sin(th) 0 0; 0 wk(2)*cos(th) 0 0; 0 0 wk(3) 0; 0 -wk(4)*0.5*sin(th)*w 0 wk(4)*near];
    R0((k-1)*nr+(1:nr))=r; Jx((k-1)*nr+(1:nr),(k-1)*4+(1:4))=J;
end
Jr=[Jx*S; sqrt(P.r)*diag(sqrt(dts/0.05))];
r0=[R0; sqrt(P.r)*sqrt(dts/0.05).*U];
H=Jr'*Jr+P.reg*eye(N); H=(H+H')/2; f=Jr'*r0;
% constraints on the step dU: input box and arm-rate box over the horizon
iv=3:4:4*N; Sv=S(iv,:); vnom=X(3,2:end)';
iw=4:4:4*N; Sw=S(iw,:); wnom=X(4,2:end)';
Ai=[eye(N);-eye(N);Sv;-Sv;Sw;-Sw]; bi=[1-U;1+U;P.vmax-vnom;P.vmax+vnom;P.wmax-wnom;P.wmax+wnom];
opt=mpcActiveSetOptions; opt.MaxIterations=200;
[dU,st]=mpcActiveSetSolver(H,f,Ai,bi,zeros(0,N),zeros(0,1),false(size(Ai,1),1),opt);
if st<=0
    [dU,st]=mpcActiveSetSolver(H,f,[eye(N);-eye(N)],[1-U;1+U],zeros(0,N),zeros(0,1),false(2*N,1),opt);
end
if st<=0, dU=zeros(N,1); end
U=max(-1,min(1,U+dU));
u=U(1);
u=round(u*c.maxCurrent/c.currentLSB)*c.currentLSB/c.maxCurrent;
% shift the nominal sequence by one control period (10 ms)
mem.U=shiftBlocks(U,dts,c.Ts);
mem.c2=mem.c1; mem.c1=u;
info.status=st; info.pred=X;
end

function Un=shiftBlocks(U,dts,Ts)
t=[0; cumsum(dts)]; tn=t(1:end-1)+Ts;           % evaluate the old piecewise-constant plan 10 ms later
Un=zeros(size(U));
for k=1:numel(U)
    j=find(tn(k)>=t(1:end-1),1,'last'); if isempty(j), j=1; end
    Un(k)=U(min(j,numel(U)));
end
end
function y=wrap(x), y=atan2(sin(x),cos(x)); end
function x=rk4(x,a,p,T)
tau=p.tau_max*a; h=p.h; n=max(1,round(T/h)); h=T/n;
for i=1:n
    k1=rhs(x); k2=rhs(x+h/2*k1); k3=rhs(x+h/2*k2); k4=rhs(x+h*k3);
    x=x+h/6*(k1+2*k2+2*k3+k4);
end
    function y=rhs(z), y=[z(3:4,:); furuta_accel(z,tau,p)]; end
end
