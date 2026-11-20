function [u,mem] = lm_controller(o,mem,D,g)
% Batched controller: constant-gain nonlinear observer -> (energy swing-up | LMPC balance).
% o: Pi observation (5 x n) [cos th; sin th; arm (rad, wrapped or raw); filt arm rate; filt pend rate]
% Only the angles are used; rates come from the observer (filter lag avoided).
% Timing: command chosen now is applied over the NEXT interval (1-step delay).
c=D.c; p=c.p; n=size(o,2);
thm=atan2(o(2,:),o(1,:)); phm=o(3,:);
if ~isfield(mem,'xh')
    mem.xh=[phm; thm; zeros(2,n)]; mem.c1=zeros(1,n); mem.c2=zeros(1,n);
    mem.bal=false(1,n); mem.home=zeros(1,n);
else
    % predict last interval (applied command = c2), then correct with measured angles
    xp=rk4(mem.xh,mem.c2,p,c);
    e=[wrap(phm-xp(1,:)); wrap(thm-xp(2,:))];
    mem.xh=xp+D.L*e;
end
xh=mem.xh;
% state at the moment the new command starts acting (one step ahead, command c1 in between)
xf=rk4(xh,mem.c1,p,c);
th=wrap(xf(2,:)); w=xf(4,:); v=xf(3,:);
% capture / release hysteresis; latch arm home on capture
cap=abs(th)<g.capAng & abs(w)<g.capRate;
newCap=cap & ~mem.bal;
mem.home(newCap)=xf(1,newCap);
mem.bal=(mem.bal & abs(th)<g.relAng) | cap;
u=zeros(1,n);
% ---- swing-up: energy pumping with arm-rate limiter (same law as the PPO expert)
sw=~mem.bal;
if any(sw)
    E=.5*p.beta2*w(sw).^2+p.delta*(cos(th(sw))-1);
    dirn=sign(w(sw).*cos(th(sw))); dirn(dirn==0)=1;
    us=g.kE*E.*dirn;
    rest=(E+2*p.delta)<g.Erest & abs(th(sw))>pi/2;
    kd=-sign(sin(th(sw))); kd(kd==0)=-1; us(rest)=kd(rest);
    vv=v(sw); over=max(0,(abs(vv)-g.v1)/(g.v2-g.v1)); same=sign(us)==sign(vv);
    us(same)=us(same).*max(0,1-over(same));
    u(sw)=us;
end
% ---- LMPC balance: box-constrained QP per balancing env
idx=find(mem.bal);
mode="lmpc"; if isfield(g,'balance'), mode=string(g.balance); end
if ~isfield(mem,'iint'), mem.iint=zeros(1,n); end
mem.iint(~mem.bal)=0;
if mode~="lmpc"
    for j=idx
        z=[max(-g.armClamp,min(g.armClamp,xf(1,j)-mem.home(j))); th(j); v(j); w(j)];
        if mode=="lqr"
            ub=-D.K*z;
        else  % PID on the pendulum angle with arm PD terms and conditional-integration anti-windup
            G=g.pid; if isfield(g,"pidScale"), G(1:4)=G(1:4)*g.pidScale; end; cand=G(1)*z(2)+G(2)*z(4)+G(3)*z(1)+G(4)*z(3)+G(5)*(mem.iint(j)+c.Ts*z(2));
            if abs(cand)<=1 || sign(cand)~=sign(z(2)), mem.iint(j)=mem.iint(j)+c.Ts*z(2); end
            ub=G(1)*z(2)+G(2)*z(4)+G(3)*z(1)+G(4)*z(3)+G(5)*mem.iint(j);
        end
        % arm-rate guard (same role as the LMPC constraint): stop pushing beyond vGuard
        if abs(v(j))>g.vGuard && sign(ub)==sign(v(j)), ub=0; end
        u(j)=ub+D.fc*p.coulomb/p.tau_max*tanh(v(j)/D.vs);
    end
    idx=[];
end
opt=mpcActiveSetOptions;
for j=idx
    z=[max(-g.armClamp,min(g.armClamp,xf(1,j)-mem.home(j))); th(j); v(j); w(j)];
    f=D.Fq*z;
    if isfinite(D.vmax)
        fv=D.Fv*z;
        Ai=[D.Aineq; D.Gv; -D.Gv]; bi=[D.bineq; D.vmax-fv; D.vmax+fv];
        [U,st]=mpcActiveSetSolver(D.H,f,Ai,bi,zeros(0,D.N),zeros(0,1),false(size(Ai,1),1),opt);
        if st<=0   % infeasible (already beyond the limit): fall back to the input-box QP
            U=mpcActiveSetSolver(D.H,f,D.Aineq,D.bineq,zeros(0,D.N),zeros(0,1),false(2*D.N,1),opt);
        end
    else
        U=mpcActiveSetSolver(D.H,f,D.Aineq,D.bineq,zeros(0,D.N),zeros(0,1),false(2*D.N,1),opt);
    end
    ub=U(1);
    ub=ub+D.fc*p.coulomb/p.tau_max*tanh(v(j)/D.vs);   % Coulomb feed-forward on predicted arm rate
    u(j)=ub;
end
u=max(-1,min(1,u));
% optional regeneration guard (hardware 2026-11-20: RMD stopped replying ~65 ms after a full
% reversal at ~8-13 rad/s): limit braking current when command opposes a fast arm, and slew-limit.
if isfield(g,'brakeMax') && isfinite(g.brakeMax)
    br=sign(u)~=sign(v) & abs(v)>g.brakeV & u~=0 & ~mem.bal;         % swing-up phase
    u(br)=sign(u(br)).*min(abs(u(br)),g.brakeMax);
end
if isfield(g,'brakeMaxBal') && isfinite(g.brakeMaxBal)
    br=sign(u)~=sign(v) & abs(v)>g.brakeVBal & u~=0 & mem.bal;       % balance phase
    u(br)=sign(u(br)).*min(abs(u(br)),g.brakeMaxBal);
end
if isfield(g,'slew') && isfinite(g.slew)
    u=mem.c1+max(-g.slew,min(g.slew,u-mem.c1));
end
% quantize like the RMD A1 path so the observer knows the applied value
u=round(u*c.maxCurrent/c.currentLSB)*c.currentLSB/c.maxCurrent;
mem.c2=mem.c1; mem.c1=u;
end

function y=wrap(x), y=atan2(sin(x),cos(x)); end
function x=rk4(x,a,p,c)
tau=p.tau_max*a; h=p.h;
for i=1:round(c.Ts/h)
    k1=rhs(x); k2=rhs(x+h/2*k1); k3=rhs(x+h/2*k2); k4=rhs(x+h*k3);
    x=x+h/6*(k1+2*k2+2*k3+k4);
end
    function y=rhs(z), y=[z(3:4,:); furuta_accel(z,tau,p)]; end
end
