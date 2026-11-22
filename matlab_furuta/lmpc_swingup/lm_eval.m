function [M,R] = lm_eval(D,g,x0,T,ev)
% Roll out lm_controller in the batched lightweight env (sp_env2) with the Pi observation path.
c=D.c; n=size(x0,2); N=round(T/c.Ts);
dr=struct('filter',ev.filter,'delayMax',1,'alpha',0,'coul',0,'eta',0);
c2=c; c2.delaySteps=ev.delay;
if isfield(ev,'plantCfg'), c2=ev.plantCfg; c2.delaySteps=ev.delay; end   % full plant swap (controller keeps D.c)
s=sp_env2.reset(x0,c2,dr); s.delay(:)=ev.delay;
if isfield(ev,'frac'), s.frac(:)=ev.frac; end
if isfield(ev,'stic'), s.coulS=s.coul.*(1+ev.stic); end                     % arm static friction (fraction above Coulomb)
if isfield(ev,'biasDeg'), s.bias=deg2rad(ev.biasDeg).*ones(1,n); [ma,mp]=sp_env2.measure(x0,s.bias); s.prev=[ma;mp]; end   % pendulum zero error
if isfield(ev,'coulTh'), s.coulTh=ev.coulTh*ones(1,n); end                 % pendulum bearing friction
if isfield(ev,'plant')   % optional plant mismatch for robustness checks
    s.alpha(:)=ev.plant(1); s.coul(:)=ev.plant(2); s.eta(:)=ev.plant(3);
end
X=zeros(4,n,N+1); X(:,:,1)=x0; A=zeros(n,N); U=zeros(n,N); mem=struct(); O=zeros(5,n,N);
for k=1:N
    [o,s]=sp_env2.observe(s,c.Ts);
    O(:,:,k)=o; [u,mem]=lm_controller(o,mem,D,g);
    [s,ap]=sp_env2.step(s,u,c2);
    X(:,:,k+1)=s.x; A(:,k)=ap; U(:,k)=u;
end
R.X=X; R.A=A; R.U=U; R.O=O; R.t=(0:N)*c.Ts;
M=sp_metrics(R,c,ev.armLim,ev.pendLim);
end
