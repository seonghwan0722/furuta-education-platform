function estimate = train_pinn_inverse(QUICK)
% 위치 측정만으로 궤적과 양수인 두 물리 파라미터를 추정한다.
arguments
    QUICK (1,1) logical = true
end
estimate = [];
has = check_toolboxes;
if ~has.deep
    fprintf('궤적 PINN 생략: Deep Learning Toolbox가 필요합니다.\n');
    return
end
rng(52,'twister');
p = furuta_params;
t = 0:p.Ts:2;
x = zeros(4,numel(t)); x(:,1) = [0;pi-.5;0;0];
for k = 1:numel(t)-1
    % 적분에서 RK4의 각 서브스텝 시각에 연속 토크를 평가한다.
    z = x(:,k);
    for j = 0:4
        tj = t(k)+j*p.h;
        a = rhs(z,tj,p);
        b = rhs(z+p.h/2*a,tj+p.h/2,p);
        c = rhs(z+p.h/2*b,tj+p.h/2,p);
        d = rhs(z+p.h*c,tj+p.h,p);
        z = z+p.h/6*(a+2*b+2*c+d);
    end
    x(:,k+1) = z;
end
take = 1:5:numel(t);
tm = t(take);
measured = x(1:2,take)+deg2rad(.3)*randn(2,numel(take));
layers = featureInputLayer(1,Normalization="none");
for k = 1:4
    layers = [layers; fullyConnectedLayer(64); tanhLayer]; %#ok<AGROW>
end
net = dlnetwork([layers; fullyConnectedLayer(2)]);
logs = dlarray(single(log([1.5*p.delta;3*p.eta_theta])));
T = dlarray(single(linspace(0,2,400)),'CB');
Tm = dlarray(single(tm),'CB');
Y = dlarray(single(measured),'CB');
lambda = .05;
epochs = 12000;
if QUICK
    epochs = 2500;
end
m = []; v = []; mp = []; vp = [];
loss = nan(epochs,3);
clock = tic;
for k = 1:epochs
    [g,gp,L,D,R] = dlfeval(@gradients,net,logs,T,Tm,Y,p,lambda);
    loss(k,:) = double([extractdata(L) extractdata(D) extractdata(R)]);
    assert(all(isfinite(loss(k,:))),'PINN 손실 발산: 학습률 또는 lambda를 줄이세요.');
    [net,m,v] = adamupdate(net,g,m,v,k,1e-3);
    [logs,mp,vp] = adamupdate(logs,gp,mp,vp,k,1e-3);
    if QUICK && toc(clock)>=300
        break
    end
end
loss = loss(1:k,:);
estimate = double(exp(extractdata(logs)));
truth = [p.delta;p.eta_theta];
errorPct = 100*abs(estimate-truth)./truth;
disp(table(["delta";"eta_theta"],estimate,truth,errorPct, ...
    'VariableNames',{'Parameter','Estimate','Truth','ErrorPct'}))
pred = extractdata(trajectory(net,dlarray(single(t),'CB')));
save(fullfile(results_dir,'pinn_inverse.mat'),'net','estimate','truth','errorPct','loss','pred','t','tm','measured','QUICK')
f = figure('Visible','off'); cleanup = onCleanup(@() close(f));
tiledlayout(f,2,1);
nexttile; semilogy(loss); grid on;
legend('합계','측정 MSE','물리 잔차'); xlabel('Adam 반복');
nexttile; plot(t,pred); hold on; plot(tm,measured,'o'); grid on;
legend('팔 예측','진자 예측','팔 측정','진자 측정');
xlabel('시간 (s)'); ylabel('각도 (rad)');
exportgraphics(f,fullfile(results_dir,'pinn_inverse.png'));
end

function z = rhs(x,t,p)
z = [x(3:4); furuta_accel(x,.015*sin(2*pi*1.2*t),p)];
end

function y = trajectory(net,t)
y = forward(net,t-1)+single([0;pi]);
end

function [g,gp,L,dataLoss,residualLoss] = gradients(net,logs,t,tm,y,p,lambda)
q = trajectory(net,t);
v1 = derivative(q(1,:),t);
v2 = derivative(q(2,:),t);
a1 = derivative(v1,t);
a2 = derivative(v2,t);
s = sin(q(2,:)); c = cos(q(2,:));
params = exp(logs);
tau = .015*sin(2*pi*1.2*t);
R1 = (p.alpha+p.beta*s.^2).*a1+p.gam*c.*a2 ...
    +2*p.beta*s.*c.*v1.*v2-p.gam*s.*v2.^2+p.eta_phi*v1-tau;
R2 = p.gam*c.*a1+p.beta2*a2-p.beta*s.*c.*v1.^2 ...
    +params(2)*v2-params(1)*s;
dataLoss = mean((trajectory(net,tm)-y).^2,'all');
residualLoss = mean((R1/p.tau_max).^2+(R2/p.delta).^2,'all');
L = dataLoss+lambda*residualLoss;
[g,gp] = dlgradient(L,net.Learnables,logs);
end

function d = derivative(y,t)
d = dlgradient(sum(y,'all'),t,EnableHigherDerivatives=true);
end
