function D = lm_design(opts)
% Linear MPC (LMPC) + constant-gain nonlinear observer design on the comparison-baseline plant.
% Plant baseline (not a confirmed measurement): alpha=0.05, eta_phi=1e-4, coulomb=0.63, 1.5 A full scale.
arguments
    opts.N (1,1) double = 20            % prediction horizon [steps of 10 ms]
    opts.Q (1,4) double = [10 10 1 1]   % [arm, pend, arm rate, pend rate]
    opts.R (1,1) double = 1
    opts.qObs (1,2) double = [50 200]   % observer process noise on [arm acc, pend acc] (rad/s^2)^2*Ts^2 scale
    opts.fc (1,1) double = 0.9          % Coulomb feed-forward fraction
    opts.vs (1,1) double = 0.05         % feed-forward smoothing [rad/s]
    opts.vmax (1,1) double = 13.5       % arm-rate constraint inside the LMPC [rad/s] (Inf = off)
    opts.plantCfg = []                  % optional full config (e.g. rev11_ident_config) used for the model
end
here=fileparts(mfilename('fullpath')); addpath(fileparts(here)); addpath(fullfile(fileparts(here),'swingup_ppo'));
c=sp_config; if ~isempty(opts.plantCfg), c=opts.plantCfg; end
p=c.p; lp=p; lp.coulomb=0;
[~,~,Ad,Bd]=furuta_linearize(lp,false);
N=opts.N; Q=diag(opts.Q); R=opts.R;
[K,P]=riccati_gain(Ad,Bd,Q,R,false);
% condensed prediction from x(k+1): X = F x + G U
n=4; F=zeros(n*N,n); G=zeros(n*N,N);
Ak=eye(n);
for i=1:N
    Ak=Ad*Ak; F((i-1)*n+(1:n),:)=Ak;
    for j=1:i
        G((i-1)*n+(1:n),j)=Ad^(i-j)*Bd;
    end
end
W=blkdiag(kron(eye(N-1),Q),P);
H=G'*W*G+R*eye(N); H=(H+H')/2;
D.Fq=G'*W*F; D.H=H; D.Ad=Ad; D.Bd=Bd; D.K=K; D.P=P; D.N=N;
D.Aineq=[eye(N);-eye(N)]; D.bineq=ones(2*N,1);
% arm-rate constraint rows over the horizon: |arm rate| <= vmax  ->  Gv U <= vmax - Fv z
iv=3:4:4*N; D.Gv=G(iv,:); D.Fv=F(iv,:); D.vmax=opts.vmax;
% steady-state observer gain (prior-to-posterior form), measurements = [arm; pend] angles
Cm=[1 0 0 0;0 1 0 0];
Ts=c.Ts; qa=opts.qObs; Qw=diag([1e-10 1e-10 qa(1)*Ts^2 qa(2)*Ts^2]);
Rv=diag([(pi/180*0.01)^2/12 (2*pi/4096)^2/12]);
Pk=eye(4);
for it=1:20000
    M=Pk-Pk*Cm'/(Cm*Pk*Cm'+Rv)*Cm*Pk;      % posterior
    Pn=Ad*M*Ad'+Qw;                           % next prior
    if norm(Pn-Pk,'fro')<1e-14, Pk=Pn; break; end
    Pk=Pn;
end
D.L=Pk*Cm'/(Cm*Pk*Cm'+Rv);
D.c=c; D.fc=opts.fc; D.vs=opts.vs; D.opts=opts;
end
