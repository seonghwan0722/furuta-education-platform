function out = sp_bc2(folder,seed,dr,K,g,tag)
% Behaviour cloning of the rate-limited energy+LQR expert (DART-style noisy execution).
rng(seed,'twister');
c=sp_config; sc=sp_scale;
nRoll=768; T=8; N=round(T/c.Ts);
x0=sp_sample_x0(nRoll,[0.55 0.15 0 0.30],[]);
x0(:,1:4)=[0 0 0 0; pi deg2rad(175) -deg2rad(175) pi; 0 0 0 0; 0 0 0 0];
s=sp_env2.reset(x0,c,dr); mem.bal=false(1,nRoll);
O=zeros(5,nRoll,N); Y=zeros(1,nRoll,N); Xs=zeros(4,nRoll,N); alive=true(1,nRoll); AL=false(nRoll,N);
noise=0.25*(rand(1,nRoll)>0.3);
for k=1:N
    [o,s]=sp_env2.observe(s,c.Ts); xo=[o(3,:); atan2(o(2,:),o(1,:)); o(4:5,:)]; [u,mem]=sp_expert(xo,mem,c,K,g);
    O(:,:,k)=o; Y(:,:,k)=u; Xs(:,:,k)=s.x; AL(:,k)=alive';
    ue=max(-1,min(1,u+noise.*randn(1,nRoll)));
    s=sp_env2.step(s,ue,c);
    alive=alive & abs(s.x(3,:))<c.armRateLimitTrain & abs(s.x(4,:))<c.pendRateLimitTrain;
end
O=reshape(O,5,[]); Y=reshape(Y,1,[]); Xs=reshape(Xs,4,[]); m=reshape(AL,1,[]);
O=O(:,m); Y=Y(m); Xs=Xs(:,m);
fprintf('BC samples %d\n',numel(Y));
% expert state bank (noise-free expert rollouts from bottom) for reset sampling
xb=sp_sample_x0(256,[1 0 0 0],[]);
R=sp_rollout(@(o,x,mm) sp_expert(x,mm,c,K,g),xb,4,c);
bank=reshape(R.X(:,:,1:2:end),4,[]);
bank=bank(:,abs(bank(3,:))<14 & abs(bank(4,:))<24);
[actor,critic,logStd]=sp_nets(64,128,0.3);
avg=[];avg2=[]; it=0; bs=4096; nS=numel(Y);
for ep=1:40
    idx=randperm(nS);
    lr=1e-3*(ep<=25)+3e-4*(ep>25);
    L=0;nb=0;
    for b=1:bs:nS-bs+1
        it=it+1; j=idx(b:b+bs-1);
        Xb=dlarray(single(O(:,j)./sc),'CB'); Yb=dlarray(single(Y(j)),'CB');
        [loss,gr]=dlfeval(@bcLoss,actor,Xb,Yb);
        [actor,avg,avg2]=adamupdate(actor,gr,avg,avg2,it,lr);
        L=L+double(extractdata(loss)); nb=nb+1;
    end
    fprintf('BC epoch %d loss %.5f\n',ep,L/nb);
end
out=struct('actor',actor,'critic',critic,'logStd',logStd,'bank',bank,'seed',seed,'K',K,'g',g);
out.dr=dr; save(fullfile(folder,['bc_' tag '.mat']),'-struct','out');
end
function [loss,gr]=bcLoss(net,X,Y)
mu=forward(net,X); loss=mean((mu-Y).^2,'all'); gr=dlgradient(loss,net.Learnables);
end
