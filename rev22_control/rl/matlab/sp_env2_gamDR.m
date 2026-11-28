classdef sp_env2
% Batched lightweight-RMD environment with the Pi observation pipeline:
%  - A1 quantization, +/-1.5 A clamp, per-env command delay (1..maxDelay steps)
%  - RK4 (h=2 ms) plant with optional per-env parameter scaling
%  - observation = furuta_pi_decode style: 12-bit pendulum encoder, 0.01 deg arm,
%    finite-difference rates with first-order filter tau=30 ms, wrapped arm angle.
methods (Static)
    function s = reset(x0,c,dr)
        n=size(x0,2); s.x=x0; s.queue=zeros(2,n); s.t=zeros(1,n);
        s.delay=ones(1,n)*c.delaySteps; s.frac=zeros(1,n); s.alpha=c.p.alpha*ones(1,n); s.coul=c.p.coulomb*ones(1,n); s.eta=c.p.eta_phi*ones(1,n);
        s.useFilter=dr.filter;
        if isfield(dr,'regenBudget') && isfinite(dr.regenBudget)
            s.regenBudget=dr.regenBudget; s.regen=zeros(1,n); s.dead=false(1,n); s.deadNew=false(1,n);
        end
        if isfield(dr,'biasDeg'), s.bias=zeros(1,n); end          % pendulum zero error (sensor/trim) [rad]
        if isfield(dr,'coulThMax'), s.coulTh=zeros(1,n); end      % pendulum bearing Coulomb friction [N m]
        if isfield(dr,'stictionMax'), s.coulS=zeros(1,n); end     % arm static friction [N m] (hardware 2026-11-20: 0.15 A did not move the arm)
        if isfield(dr,'gam'), s.gam=c.p.gam*ones(1,n); end           % coupling-term randomization (rev22, 2026-11-28)
        s = sp_env2.randomize(s,true(1,n),dr,c);
        [ma,mp]=sp_env2.measure(x0,sp_env2.biasOf(s,true(1,n))); s.prev=[ma;mp]; s.filt=x0(3:4,:);
    end
    function s = randomize(s,m,dr,c)
        n=nnz(m); if n==0, return; end
        if dr.delayMax>1, s.delay(m)=randi([1 dr.delayMax],1,n); else, s.delay(m)=c.delaySteps; end
        if isfield(dr,'fracMax') && dr.fracMax>0, s.frac(m)=dr.fracMax*rand(1,n); end
        if isfield(dr,'tauRange')   % optional filter-tau curriculum; absent -> 30 ms everywhere
            if ~isfield(s,'tau'), s.tau=.03*ones(1,numel(s.frac)); end
            s.tau(m)=dr.tauRange(1)+(dr.tauRange(2)-dr.tauRange(1))*rand(1,n);
        end
        if isfield(dr,'biasDeg'), s.bias(m)=deg2rad(dr.biasDeg)*(2*rand(1,n)-1); end
        if isfield(dr,'coulThMax'), s.coulTh(m)=dr.coulThMax*rand(1,n); end
        s.alpha(m)=c.p.alpha*(1+dr.alpha*(2*rand(1,n)-1));
        s.coul(m)=c.p.coulomb*(1+dr.coul*(2*rand(1,n)-1));
        s.eta(m)=c.p.eta_phi*(1+dr.eta*(2*rand(1,n)-1));
        if isfield(dr,'stictionMax'), s.coulS(m)=s.coul(m).*(1+dr.stictionMax*rand(1,n)); end
        if isfield(dr,'gam'), s.gam(m)=c.p.gam*(1+dr.gam*(2*rand(1,n)-1)); end   % drawn last: older configs keep their random stream
    end
    function s = resetSome(s,m,xn,dr,c)
        s.x(:,m)=xn; s.queue(:,m)=0; s.t(m)=0;
        if isfield(s,'regenBudget'), s.regen(m)=0; s.dead(m)=false; s.deadNew(m)=false; end
        s=sp_env2.randomize(s,m,dr,c);
        [ma,mp]=sp_env2.measure(xn,sp_env2.biasOf(s,m)); s.prev(:,m)=[ma;mp]; s.filt(:,m)=xn(3:4,:);
    end
    function [ma,mp] = measure(x,bias)
        if nargin<2, bias=0; end
        ma=round(rad2deg(x(1,:))*100)/100*pi/180;
        cnt=mod(round((x(2,:)+bias)/(2*pi)*4096),4096); mp=cnt*2*pi/4096; mp=atan2(sin(mp),cos(mp));
    end
    function b = biasOf(s,m)
        if isfield(s,'bias'), b=s.bias(m); else, b=0; end
    end
    function [o,s] = observe(s,Ts)
        % called once per control tick, BEFORE the action is chosen
        [ma,mp]=sp_env2.measure(s.x,sp_env2.biasOf(s,true(1,size(s.x,2))));
        if s.useFilter
            d=[ma;mp]-s.prev; d(2,:)=atan2(sin(d(2,:)),cos(d(2,:)));
            tau=.03; if isfield(s,'tau'), tau=s.tau; end   % per-env filter tau (default = Pi decode 30 ms)
            s.filt=s.filt+(Ts./(tau+Ts)).*(d/Ts-s.filt);
            rates=s.filt;
        else
            rates=s.x(3:4,:);
        end
        s.prev=[ma;mp];
        o=[cos(mp); sin(mp); atan2(sin(ma),cos(ma)); rates];
    end
    function [s,applied] = step(s,a,c)
        a=max(-1,min(1,a));
        counts=round(a*c.maxCurrent/c.currentLSB); lim=floor(c.maxCurrent/c.currentLSB+1e-9);
        cmd=max(-lim,min(lim,counts))*c.currentLSB/c.maxCurrent;
        applied=s.queue(1,:); two=s.delay==2; applied(two)=s.queue(2,two);
        older=s.queue(2,:);
        s.queue=[cmd; s.queue(1,:)];
        tauNew=c.p.tau_max*applied; tauOld=c.p.tau_max*older;
        if isfield(s,'regenBudget')
            % hardware 2026-11-20: braking energy per event above ~1 J made the RMD stop responding.
            % Model: accumulate braking energy while the applied torque opposes the arm; over budget -> motor dead.
            pb=max(0,-tauNew.*s.x(3,:))*c.Ts;
            s.regen=(pb>0).*(s.regen+pb);
            s.deadNew=~s.dead & s.regen>s.regenBudget; s.dead=s.dead | s.deadNew;
            tauNew(s.dead)=0; tauOld(s.dead)=0;
        end
        nOld=round(s.frac*round(c.Ts/c.p.h));
        p=c.p; p.alpha=s.alpha; p.coulomb=s.coul; p.eta_phi=s.eta;
        if isfield(s,'coulTh'), p.coulTh=s.coulTh; end
        if isfield(s,'gam'), p.gam=s.gam; end
        x=s.x; h=p.h;
        for i=1:round(c.Ts/h)
            tau=tauNew; o=i<=nOld; tau(o)=tauOld(o);
            if isfield(s,'coulS'), stk=abs(x(3,:))<1e-3 & abs(tau)<s.coulS; tau(stk)=0; x(3,stk)=0; else, stk=false(1,size(x,2)); end
            k1=rhs(x); k2=rhs(x+h/2*k1); k3=rhs(x+h/2*k2); k4=rhs(x+h*k3);
            x=x+h/6*(k1+2*k2+2*k3+k4);
            if any(stk), x(3,stk)=0; x(1,stk)=x(1,stk)-h/6*(k1(1,stk)+2*k2(1,stk)+2*k3(1,stk)+k4(1,stk)); end
        end
        s.x=x; s.t=s.t+c.Ts;
        function y=rhs(z), y=[z(3:4,:); accel(z,tau,p)]; end
    end
end
end
function a = accel(x,tau,p)
s=sin(x(2,:)); c=cos(x(2,:)); v=x(3,:); w=x(4,:);
d=p.alpha+p.beta*s.^2; b=p.gam.*c;
f=tau-2*p.beta*s.*c.*v.*w+p.gam.*s.*w.^2-p.eta_phi.*v-p.coulomb.*sign(v);
g=p.beta*s.*c.*v.^2-p.eta_theta*w+p.delta*s;
if isfield(p,'coulTh'), g=g-p.coulTh.*tanh(w/0.05); end   % smoothed pendulum bearing friction
detD=d*p.beta2-b.^2;
a=[(p.beta2*f-b.*g)./detD; (d.*g-b.*f)./detD];
end
