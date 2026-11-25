function sp_ppo(folder,init,cfg)
% Custom batched PPO (clipped surrogate, GAE) on the lightweight RMD env.
% Saves checkpoints + evaluation logs every cfg.evalEvery iterations.
rng(cfg.seed,'twister');
c=sp_config; sc=single(sp_scale);
actor=init.actor; critic=init.critic; logStd=dlarray(single(log(cfg.std0)));
if isfield(init,'logStd') && cfg.keepStd, logStd=init.logStd; end
bank=init.bank;
nE=cfg.nEnv; T=cfg.horizon; maxSteps=round(cfg.episodeSeconds/c.Ts);
x0=sp_sample_x0(nE,cfg.mix,bank); s=sp_env.reset(x0,c); epT=zeros(1,nE); epR=zeros(1,nE);
aA=[];aA2=[];aC=[];aC2=[];aS=[];aS2=[]; it=0;
logT=table(); doneR=[]; nTerm=0; nEp=0;
evalStarts=deg2rad([180 175 -175 172 -168 163 -158 13 -13 8 -4]);
xe=[zeros(1,numel(evalStarts)); evalStarts; zeros(2,numel(evalStarts))];
for iter=1:cfg.iters
    O=zeros(5,nE,T,'single'); A=zeros(1,nE,T,'single'); LP=zeros(1,nE,T,'single');
    V=zeros(1,nE,T,'single'); Rw=zeros(1,nE,T,'single'); D=zeros(1,nE,T,'single');
    for k=1:T
        o=single(sp_env.obs(s.x));
        mu=extractdata(predict(actor,dlarray(o./sc,'CB')));
        vv=extractdata(predict(critic,dlarray(o./sc,'CB')));
        sd=exp(extractdata(logStd));
        a=mu+sd.*randn(1,nE,'single');
        lp=-0.5*((a-mu)./sd).^2-log(sd)-0.5*log(2*pi);
        s=sp_env.step(s,double(a),c);
        [r,term]=sp_reward(s.x,max(-1,min(1,double(a))),c,cfg.rw);
        epT=epT+1; epR=epR+r;
        trunc=~term & epT>=maxSteps;
        if any(trunc) % bootstrap truncated episodes
            ot=single(sp_env.obs(s.x(:,trunc)));
            r(trunc)=r(trunc)+cfg.gamma*double(extractdata(predict(critic,dlarray(ot./sc,'CB'))));
        end
        fin=term|trunc;
        O(:,:,k)=o; A(:,:,k)=a; LP(:,:,k)=lp; V(:,:,k)=vv; Rw(:,:,k)=r; D(:,:,k)=fin;
        if any(fin)
            doneR=[doneR epR(fin)]; nTerm=nTerm+nnz(term); nEp=nEp+nnz(fin); %#ok<AGROW>
            nf=nnz(fin); xn=sp_sample_x0(nf,cfg.mix,bank);
            s.x(:,fin)=xn; s.queue(:,fin)=0; epT(fin)=0; epR(fin)=0;
        end
    end
    vLast=extractdata(predict(critic,dlarray(single(sp_env.obs(s.x))./sc,'CB')));
    % GAE
    Adv=zeros(1,nE,T,'single'); gae=zeros(1,nE,'single');
    for k=T:-1:1
        if k==T, vn=vLast; else, vn=V(:,:,k+1); end
        nd=1-D(:,:,k);
        delta=Rw(:,:,k)+cfg.gamma*vn.*nd-V(:,:,k);
        gae=delta+cfg.gamma*cfg.lambda*nd.*gae;
        Adv(:,:,k)=gae;
    end
    Ret=Adv+V;
    O=reshape(O,5,[]); A=reshape(A,1,[]); LP=reshape(LP,1,[]); Adv=reshape(Adv,1,[]); Ret=reshape(Ret,1,[]);
    Adv=(Adv-mean(Adv))/(std(Adv)+1e-8);
    nS=numel(A); bs=cfg.miniBatch; kls=[];
    updActor = iter>cfg.criticWarmup;
    for ep=1:cfg.epochs
        idx=randperm(nS);
        for b=1:bs:nS-bs+1
            it=it+1; j=idx(b:b+bs-1);
            Xb=dlarray(O(:,j)./sc,'CB');
            [lossA,lossC,gA,gC,gS,kl]=dlfeval(@ppoLoss,actor,critic,logStd,Xb,A(j),LP(j),Adv(j),Ret(j),cfg);
            [critic,aC,aC2]=adamupdate(critic,gC,aC,aC2,it,cfg.lrC);
            if updActor
                [actor,aA,aA2]=adamupdate(actor,gA,aA,aA2,it,cfg.lrA);
                if cfg.learnStd
                    [logStd,aS,aS2]=adamupdate(logStd,gS,aS,aS2,it,cfg.lrA);
                    logStd=max(log(cfg.stdMin),logStd);
                end
            end
            kls(end+1)=double(extractdata(kl)); %#ok<AGROW>
        end
        if updActor && mean(kls)>cfg.targetKL, break; end
    end
    meanEp=NaN; if ~isempty(doneR), meanEp=mean(doneR); end
    fprintf('IT %d epR %.1f nEp %d term %d KL %.4f std %.3f lossC %.3f\n',iter,meanEp,nEp,nTerm,mean(kls),exp(double(extractdata(logStd))),double(extractdata(lossC)));
    row=table(iter,meanEp,nEp,nTerm,mean(kls),exp(double(extractdata(logStd))),'VariableNames',{'Iter','MeanEpReturn','Episodes','Terminations','KL','Std'});
    doneR=[]; nEp=0; nTerm=0;
    if mod(iter,cfg.evalEvery)==0 || iter==cfg.iters
        M=sp_policy_eval(actor,xe,25,c);
        row.EvalPass=nnz(M.Passed); row.EvalN=height(M);
        row.EvalMaxHoldErr=max(M.HoldMaxErrDeg); row.EvalMaxArm=max(M.PeakArmRate);
        fprintf('EVAL it %d pass %d/%d maxHoldErr %.2f maxArm %.2f maxPend %.2f reach %s\n',iter,nnz(M.Passed),height(M), ...
            max(M.HoldMaxErrDeg),max(M.PeakArmRate),max(M.PeakPendRate),mat2str(M.ReachTime',3));
        ck=struct('actor',actor,'critic',critic,'logStd',logStd,'iter',iter,'cfg',cfg,'eval',M,'bank',bank);
        save(fullfile(folder,sprintf('ck_%04d.mat',iter)),'-struct','ck');
    else
        row.EvalPass=NaN; row.EvalN=NaN; row.EvalMaxHoldErr=NaN; row.EvalMaxArm=NaN;
    end
    logT=[logT; row]; %#ok<AGROW>
    writetable(logT,fullfile(folder,'train_log.csv'));
end
end

function [lossA,lossC,gA,gC,gS,kl]=ppoLoss(actor,critic,logStd,X,A,LP,Adv,Ret,cfg)
mu=forward(actor,X); v=forward(critic,X);
sd=exp(logStd);
lp=-0.5*((A-mu)./sd).^2-logStd-0.5*log(2*pi);
ratio=exp(lp-LP);
s1=ratio.*Adv; s2=min(max(ratio,1-cfg.clip),1+cfg.clip).*Adv;
ent=logStd+0.5*log(2*pi*exp(1));
% keep the mean inside the actuator range (tanh output already bounded)
lossA=-mean(min(s1,s2),'all')-cfg.entropy*ent;
lossC=0.5*mean((v-Ret).^2,'all');
kl=mean(LP-lp,'all');
[gA,gS]=dlgradient(lossA,actor.Learnables,logStd);
gC=dlgradient(lossC,critic.Learnables);
end
