function T = sp_linear_feasibility(taus)
if nargin<1, taus=0.03; end
% Static output-feedback feasibility at the upright, with the Pi observation pipeline.
c=sp_config; lp=c.p; lp.coulomb=0;
[Ad,Bd]=lin(lp,c);          % 4-state ZOH discretization, input = normalized action
rows={};
for delay=[1 2]
 for tau=taus
  filt=tau>0;
  for withPrev=[false]
   [A,B,C]=augment(Ad,Bd,delay,filt,withPrev,c.Ts,tau);
   K0=dlqrK(Ad,Bd);
   F0=initF(K0,C,size(A,1),delay,filt,withPrev);
   obj=@(f) max(abs(eig(A-B*f(:).'*C)));
   best=inf; bestF=F0;
   for trial=1:10
     f0=F0.*(1+0.5*(trial>1)*randn(size(F0)));
     opt=optimset('MaxFunEvals',6000,'MaxIter',6000,'TolX',1e-7,'TolFun',1e-9,'Display','off');
     [f,v]=fminsearch(obj,f0,opt);
     if v<best, best=v; bestF=f; end
   end
   rows(end+1,:)={delay,tau,withPrev,obj(F0),best,mat2str(bestF,4)}; %#ok<AGROW>
  end
 end
end
T=cell2table(rows,'VariableNames',{'Delay','FilterTau','PrevActionObs','RhoLQRinit','RhoBest','Gain'});
disp(T)
end
function [Ad,Bd]=lin(p,c)
[~,~,A,B]=furuta_linearize(p,false); Ad=A; Bd=B; % furuta_linearize returns discrete (per riccati use)
end
function K=dlqrK(A,B), K=riccati_gain(A,B,diag([10 10 1 1]),1,false); end
function [A,B,C]=augment(Ad,Bd,delay,filt,withPrev,Ts,tau)
% states: x(4), queue(delay), prevAngles(2) if filt, filt(2) if filt
n=4; nq=delay; nf=2*filt; np=2*filt; N=n+nq+np+nf;
A=zeros(N); B=zeros(N,1);
iq=n+(1:nq); ip=n+nq+(1:np); iff=n+nq+np+(1:nf);
% plant
A(1:n,1:n)=Ad;
if delay==0, B(1:n)=Bd; else, A(1:n,iq(end))=Bd; end
% queue: q1 <- u, q2 <- q1 ; applied = q_last
if delay>=1, B(iq(1))=1; end
for k=2:nq, A(iq(k),iq(k-1))=1; end
if filt
    a=Ts/(tau+Ts);
    % prev angles <- current angles (x1,x2)
    A(ip,1:n)=[1 0 0 0;0 1 0 0];
    % f_{k+1} = (1-a) f_k + a*(ang_{k+1}-ang_k)/Ts ; ang_{k+1} = rows 1:2 of A*z+B*u
    Mang=[eye(2) zeros(2,N-2)];
    A(iff,:)=a/Ts*(Mang*A - Mang);
    A(iff,iff)=A(iff,iff)+(1-a)*eye(2);
    B(iff)=a/Ts*(Mang*B);
end
% outputs: phi, theta, rates (filtered or true), optional previous action
if filt, C=[eye(2) zeros(2,N-2); zeros(2,N-nf) eye(2)];
else, C=[eye(4) zeros(4,N-4)]; end
if withPrev
    r=zeros(1,N); if delay>=1, r(iq(1))=1; end
    C=[C; r];
end
end
function F=initF(K,C,N,delay,filt,withPrev)
F=K; if withPrev, F=[K 0]; end
end
