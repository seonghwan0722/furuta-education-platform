function [u,mem,info] = lm_ms_controller(o,mem,D,P)
% Stage-2 controller: linear MPC re-linearized every control step along a MULTIPLE-SHOOTING
% trajectory (one QP per step, real-time-iteration style, Gauss-Newton cost). No separate swing-up law.
% Multiple shooting keeps the unstable pendulum well conditioned over a long horizon.
c=D.c; p=c.p; pl=p; pl.coulomb=0;
thm=atan2(o(2),o(1)); phm=o(3);
dts=P.dts(:); N=numel(dts);
if ~isfield(mem,'xh')
    mem.xh=[phm;thm;0;0]; mem.c1=0; mem.c2=0;
    mem.U=P.U0(:); mem.S=[];
else
    xp=rk4(mem.xh,mem.c2,p,c.Ts);
    e=[wrap(phm-xp(1)); wrap(thm-xp(2))];
    mem.xh=xp+D.L*e;
end
xf=rk4(mem.xh,mem.c1,p,c.Ts);
U=mem.U;
if isempty(mem.S)                       % initial nodes: simulate the initial input guess
    S=zeros(4,N+1); S(:,1)=xf;
    for k=1:N, S(:,k+1)=rk4(S(:,k),U(k),p,dts(k)); end
else
    S=mem.S; S(:,1)=xf;
end
S(2,:)=unwrapNear(S(2,:),xf(2));
nIt=P.iters;
for itn=1:nIt
    A=zeros(4,4,N); B=zeros(4,N); F=zeros(4,N); ep=1e-5;
    for k=1:N
        F(:,k)=rk4(S(:,k),U(k),p,dts(k));
        Z=[S(:,k) S(:,k)+ep*eye(4) S(:,k)]; a=[U(k)*ones(1,5) U(k)+ep];
        Y=rk4(Z,a,pl,dts(k));
        A(:,:,k)=(Y(:,2:5)-Y(:,1))/ep; B(:,k)=(Y(:,6)-Y(:,1))/ep;
    end
    % variables: [dx_1..dx_N (4N); du_1..du_N (N)], dx_0 = 0 (node 0 fixed to xf)
    nx=4*N; nv=nx+N;
    Hq=zeros(nv); fq=zeros(nv,1);
    for k=1:N
        x=S(:,k+1); th=x(2); w=x(4); v=x(3); wk=P.w; if k==N, wk=wk*P.terminal; end
        s=sqrt(dts(k)/0.05); near=(1+cos(th))/2;
        r=s*[wk(1)*(1-cos(th)); wk(2)*sin(th); wk(3)*v; wk(4)*near*w];
        J=s*[0 wk(1)*sin(th) 0 0; 0 wk(2)*cos(th) 0 0; 0 0 wk(3) 0; 0 -wk(4)*0.5*sin(th)*w 0 wk(4)*near];
        ix=(k-1)*4+(1:4); iu=nx+k;
        Hq(ix,ix)=Hq(ix,ix)+J'*J; fq(ix)=fq(ix)+J'*r;
        Hq(iu,iu)=Hq(iu,iu)+P.r*dts(k)/0.05; fq(iu)=fq(iu)+P.r*dts(k)/0.05*U(k);
    end
    Hq=Hq+P.reg*eye(nv); Hq=(Hq+Hq')/2;
    % dynamics: dx_k - A_k dx_{k-1} - B_k du_k = F_k - S_k   (defect)
    Aeq=zeros(nx,nv); beq=zeros(nx,1);
    for k=1:N
        ix=(k-1)*4+(1:4);
        Aeq(ix,ix)=eye(4);
        if k>1, Aeq(ix,(k-2)*4+(1:4))=-A(:,:,k); end
        Aeq(ix,nx+k)=-B(:,k);
        d=F(:,k)-S(:,k+1); d(2)=wrap(d(2));
        beq(ix)=d;
    end
    % inequalities: input box, arm-rate and pendulum-rate bounds at the nodes
    E3=zeros(N,nv); E4=zeros(N,nv); Eu=zeros(N,nv);
    for k=1:N, E3(k,(k-1)*4+3)=1; E4(k,(k-1)*4+4)=1; Eu(k,nx+k)=1; end
    v0=S(3,2:end)'; w0=S(4,2:end)';
    Ai=[Eu;-Eu;E3;-E3;E4;-E4];
    bi=[1-U;1+U;P.vmax-v0;P.vmax+v0;P.wmax-w0;P.wmax+w0];
    opt=mpcActiveSetOptions; opt.MaxIterations=500;
    [z,st]=mpcActiveSetSolver(Hq,fq,Ai,bi,Aeq,beq,false(size(Ai,1),1),opt);
    if st<=0   % drop the rate bounds if infeasible
        [z,st]=mpcActiveSetSolver(Hq,fq,[Eu;-Eu],[1-U;1+U],Aeq,beq,false(2*N,1),opt);
    end
    if st<=0, break; end
    S(:,2:end)=S(:,2:end)+reshape(z(1:nx),4,N);
    U=max(-1,min(1,U+z(nx+1:end)));
end
u=U(1);
u=round(u*c.maxCurrent/c.currentLSB)*c.currentLSB/c.maxCurrent;
% shift nodes/inputs by one 10 ms control period (fine blocks shift, coarse blocks kept)
nf=P.nFine;
Un=U; Sn=S;
Un(1:nf-1)=U(2:nf); Sn(:,1:nf)=S(:,2:nf+1);
mem.U=Un; mem.S=Sn;
mem.c2=mem.c1; mem.c1=u;
info.status=st; info.pred=S;
end

function y=unwrapNear(th,ref)
y=th; y(1)=ref;
for k=2:numel(th), y(k)=y(k-1)+wrap(th(k)-y(k-1)); end
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
