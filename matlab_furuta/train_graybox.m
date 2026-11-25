function net = train_graybox(QUICK)
% 쿨롱 마찰이 있는 플랜트의 10단계 예측으로 가속도 보정망을 학습한다.
arguments
    QUICK (1,1) logical = true
end
net = [];
has = check_toolboxes;
if ~has.deep
    fprintf('회색상자 학습 생략: Deep Learning Toolbox가 필요합니다.\n');
    return
end
rng(53,'twister');
p = furuta_params; realPlant = p; realPlant.coulomb = .002;
horizon = 10; rollouts = 2400; iterations = 3000;
if QUICK
    rollouts = 600; iterations = 500;
end
% 무작위 상태에서 짧은 궤적을 시작해 직립과 아래쪽 데이터를 모두 얻는다.
X = zeros(4,rollouts,horizon+1,'single');
U = single(2*rand(horizon,rollouts)-1);
X(:,:,1) = single([2*rand(1,rollouts)-1; ...
    .7*randn(1,rollouts)+pi*(rand(1,rollouts)<.3); ...
    8*randn(2,rollouts)]);
for j = 1:horizon
    X(:,:,j+1) = furuta_step(X(:,:,j),U(j,:),realPlant);
end
layers = [featureInputLayer(6,Normalization="none")
    fullyConnectedLayer(32)
    tanhLayer
    fullyConnectedLayer(32)
    tanhLayer
    fullyConnectedLayer(2)];
net = dlnetwork(layers);
m = []; v = [];
loss = nan(iterations,3);
clock = tic;
for k = 1:iterations
    batch = randperm(rollouts,32);
    [g,L,e,r] = dlfeval(@gradients,net,X(:,batch,:),U(:,batch),p);
    loss(k,:) = double([extractdata(L) extractdata(e) extractdata(r)]);
    assert(all(isfinite(loss(k,:))),'회색상자 손실 발산: 학습률 또는 초기 속도 범위를 줄이세요.');
    [net,m,v] = adamupdate(net,g,m,v,k,5e-4);
    if QUICK && toc(clock)>=300
        break
    end
end
loss = loss(1:k,:);
fprintf('회색상자 학습 %d회, %.1f초\n',k,toc(clock));
save(fullfile(results_dir,'graybox.mat'),'net','loss','QUICK')
f = figure('Visible','off'); cleanup = onCleanup(@() close(f));
semilogy(loss); grid on; xlabel('Adam 반복'); ylabel('손실');
legend('합계','롤아웃 오차','가속도 보정 정규화');
exportgraphics(f,fullfile(results_dir,'graybox_learning.png'));
end

function [g,L,fit,reg] = gradients(net,target,u,p)
x = dlarray(target(:,:,1)); fit = 0; reg = 0;
n = size(u,1);
for j = 1:n
    input = u(j,:);
    reg = reg+mean((gray_correction(net,x,input)/100).^2,'all');
    x = furuta_step(x,input,p,0,@(z,a) gray_correction(net,z,a));
    residual = (x-target(:,:,j+1))./single([.2;.2;10;10]);
    fit = fit+mean(residual.^2,'all');
end
fit = fit/n; reg = reg/n;
L = fit+1e-3*reg;
g = dlgradient(L,net.Learnables);
end
