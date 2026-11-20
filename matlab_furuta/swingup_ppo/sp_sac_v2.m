function sp_sac_v2(folder,init,cfg)
% v2 (literature-aligned): AR(1) temporally-correlated exploration noise (gSDE-like, cfg.noiseRho),
% UTD ~1, actor updated every cfg.actorEvery critic steps. Otherwise as sp_sac_asym.
% Batched SAC with an ASYMMETRIC critic: actor sees the Pi observation (filtered rates),
% the twin critics also see the true rates and the two queued (not yet applied) commands.
% n-step returns, TD3+BC-style behaviour regularization, fixed or auto entropy.
rng(cfg.seed,'twister');
c=sp_config; sc=single(sp_scale);
if isfield(cfg,'plantFn'), c=feval(cfg.plantFn); end
if isfield(cfg,'armLimTrain'), c.armRateLimitTrain=cfg.armLimTrain; end
if isfield(cfg,'pendLimTrain'), c.pendRateLimitTrain=cfg.pendLimTrain; end   % stricter training trip; eval keeps 25
if isfield(init,'sacActor'), actor=init.sacActor; else, actor=sacActorFromBC(init.actor,cfg.std0); end
ref=actor;
nC=9; q1=qnet(nC+1,256); q2=qnet(nC+1,256);
if isfield(cfg,'keepCritics') && cfg.keepCritics && isfield(init,'q1'), q1=init.q1; q2=init.q2; end
t1=q1; t2=q2;
logA=dlarray(single(log(cfg.alpha0)));
nE=cfg.nEnv; maxSteps=round(cfg.episodeSeconds/c.Ts); B=cfg.buffer; ns=cfg.nstep;
bo=zeros(5,B,'single'); bc=zeros(nC,B,'single'); ba=zeros(1,B,'single'); br=zeros(1,B,'single');
bn=zeros(5,B,'single'); bcn=zeros(nC,B,'single'); bd=zeros(1,B,'single'); bg=zeros(1,B,'single');
ptr=0; full=false;
x0=sp_sample_x0(nE,cfg.mix,init.bank); s=sp_env2.reset(x0,c,cfg.dr); epT=randi(maxSteps,1,nE); epR=zeros(1,nE);
[o,s]=sp_env2.observe(s,c.Ts); o=single(o)./sc; en=randn(1,nE,'single');
aA=[];aA2=[];a1=[];a12=[];a2=[];a22=[];aL=[];aL2=[]; it=0; logT=table(); doneR=[];
evalStarts=deg2rad([180 175 -175 177 -172 168 -165 160 -156 150 -145 13 -13 8 -4 0]);
xe=[zeros(1,numel(evalStarts)); evalStarts; zeros(2,numel(evalStarts))];
for iter=1:cfg.iters
    T=cfg.stepsPerIter;
    CO=zeros(5,nE,T,'single'); CC=zeros(nC,nE,T,'single'); CA=zeros(1,nE,T,'single'); CR=zeros(nE,T);
    CT=false(nE,T); CF=false(nE,T); CN=zeros(5,nE,T,'single'); CCN=zeros(nC,nE,T,'single');
    for k=1:T
        co=critObs(o,s);
        yy=extractdata(predict(actor,dlarray(o,'CB'))); sdv=exp(max(-5,min(1,yy(2,:))));
        en=cfg.noiseRho*en+sqrt(1-cfg.noiseRho^2)*randn(1,nE,'single');
        a=tanh(yy(1,:)+sdv.*en);
        aprev=s.queue(1,:);
        s=sp_env2.step(s,double(a),c);
        [r,term]=sp_reward(s.x,double(a),c,cfg.rw);
        if isfield(s,'deadNew'), term=term|s.deadNew; r(s.deadNew)=-cfg.rw.termPenalty; end
        if isfield(cfg.rw,'regen') && isfield(s,'regen'), r(~term)=r(~term)-cfg.rw.regen*s.regen(~term); end
        r(~term)=r(~term)-cfg.rw.du*(double(a(~term))-aprev(~term)).^2;
        epT=epT+1; epR=epR+r; trunc=~term & epT>=maxSteps;
        [o2,s]=sp_env2.observe(s,c.Ts); o2=single(o2)./sc;
        fin=term|trunc;
        CO(:,:,k)=o; CC(:,:,k)=co; CA(:,:,k)=a; CR(:,k)=r; CT(:,k)=term; CF(:,k)=fin;
        CN(:,:,k)=o2; CCN(:,:,k)=critObs(o2,s);
        if any(fin)
            doneR=[doneR epR(fin)]; %#ok<AGROW>
            xn=sp_sample_x0(nnz(fin),cfg.mix,init.bank); s=sp_env2.resetSome(s,fin,xn,cfg.dr,c);
            epT(fin)=0; epR(fin)=0; en(fin)=randn(1,nnz(fin),'single');
            [ob,sb]=sp_env2.observe(s,c.Ts); ob=single(ob)./sc; o2(:,fin)=ob(:,fin); s.filt=sb.filt; s.prev=sb.prev;
        end
        o=o2;
    end
    for k=1:T
        G=zeros(nE,1); disc=ones(nE,1); done=false(nE,1); stop=false(nE,1);
        nxt=CN(:,:,k); nxc=CCN(:,:,k);
        for m=0:ns-1
            kk=k+m; if kk>T, break; end
            act=~stop; G(act)=G(act)+disc(act).*CR(act,kk); disc(act)=disc(act)*cfg.gamma;
            nxt(:,act)=CN(:,act,kk); nxc(:,act)=CCN(:,act,kk); done(act)=CT(act,kk); stop=stop|CF(:,kk);
        end
        idx=mod(ptr+(0:nE-1),B)+1; ptr=mod(ptr+nE,B); if ptr<nE, full=true; end
        bo(:,idx)=CO(:,:,k); bc(:,idx)=CC(:,:,k); ba(idx)=CA(:,:,k); br(idx)=G;
        bn(:,idx)=nxt; bcn(:,idx)=nxc; bd(idx)=done; bg(idx)=disc;
    end
    n=B; if ~full, n=ptr; end
    for u=1:cfg.updatesPerIter
        it=it+1; j=randi(n,1,cfg.batch);
        O=dlarray(bo(:,j),'CB'); C=dlarray(bc(:,j),'CB'); A=dlarray(ba(j),'CB');
        O2=dlarray(bn(:,j),'CB'); C2=dlarray(bcn(:,j),'CB');
        al=exp(extractdata(logA));
        [a2n,lp2]=sampleAct(actor,O2);
        qt=min(predict(t1,[C2;a2n]),predict(t2,[C2;a2n]));
        y=dlarray(br(j)+bg(j).*(1-bd(j)).*extractdata(qt-al*lp2),'CB');
        [g1,g2]=dlfeval(@qLoss2,q1,q2,C,A,y);
        [q1,a1,a12]=adamupdate(q1,g1,a1,a12,it,cfg.lrQ); [q2,a2,a22]=adamupdate(q2,g2,a2,a22,it,cfg.lrQ);
        if iter>cfg.actorWarmup && mod(u,cfg.actorEvery)==0
            bcW=0; aRef=[];
            if cfg.bcW>0
                bcW=cfg.bcW*max(cfg.bcMin,1-(iter-cfg.actorWarmup)/cfg.bcDecay);
                yr=predict(ref,O); aRef=tanh(yr(1,:));
            end
            [gA,ent]=dlfeval(@piLoss,actor,q1,q2,O,C,al,bcW,aRef);
            [actor,aA,aA2]=adamupdate(actor,gA,aA,aA2,it,cfg.lrA);
            if cfg.autoAlpha
                gL=dlfeval(@alphaGrad,logA,ent,cfg.targetEnt);
                [logA,aL,aL2]=adamupdate(logA,gL,aL,aL2,it,cfg.lrAlpha);
            end
        end
        t1=soft(t1,q1,cfg.tau); t2=soft(t2,q2,cfg.tau);
    end
    meanEp=NaN; if ~isempty(doneR), meanEp=mean(doneR); end
    fprintf('IT %d epR %.1f nEp %d alpha %.4f\n',iter,meanEp,numel(doneR),exp(extractdata(logA)));
    row=table(iter,meanEp,numel(doneR),exp(double(extractdata(logA))),'VariableNames',{'Iter','MeanEpReturn','Episodes','Alpha'});
    doneR=[]; row.EvalPass=NaN; row.EvalPassD2=NaN;
    if mod(iter,cfg.evalEvery)==0
        det=sp_sac_det(actor);
        rb=Inf; if isfield(cfg.dr,'regenBudget'), rb=cfg.dr.regenBudget; end
        M1=sp_eval2(det,xe,25,c,struct('filter',cfg.dr.filter,'delay',1,'armLim',15,'pendLim',25,'frac',0,'regenBudget',rb));
        M2=sp_eval2(det,xe,25,c,struct('filter',true,'delay',1,'armLim',15,'pendLim',25,'frac',1,'regenBudget',rb));
        row.EvalPass=nnz(M1.Passed); row.EvalPassD2=nnz(M2.Passed);
        fprintf('EVAL it %d d1 pass %d/16 d2 pass %d maxArm %.2f\n',iter,nnz(M1.Passed),nnz(M2.Passed),max(M1.PeakArmRate));
        ck=struct('actor',det,'sacActor',actor,'q1',q1,'q2',q2,'logAlpha',logA,'iter',iter,'cfg',cfg, ...
            'eval',M1,'evalD2',M2,'bank',init.bank,'critic',init.critic,'logStd',dlarray(single(log(0.1))));
        save(fullfile(folder,sprintf('ck_%04d.mat',iter)),'-struct','ck');
    end
    logT=[logT;row]; %#ok<AGROW>
    writetable(logT,fullfile(folder,'train_log.csv'));
end
end

function z=critObs(o,s)
% privileged critic input: actor obs (scaled) + true rates + queued commands
z=[o; single(s.x(3:4,:))/10; single(s.queue)];
end
function net=sacActorFromBC(bc,std0)
P=bc.Learnables; W=@(l,p) single(extractdata(P.Value{P.Layer==l & P.Parameter==p}));
W3=W("fc3","Weights"); b3=W("fc3","Bias");
net=dlnetwork([featureInputLayer(5,Name="obs") ...
    fullyConnectedLayer(64,Name="fc1",Weights=W("fc1","Weights"),Bias=W("fc1","Bias")) tanhLayer(Name="t1") ...
    fullyConnectedLayer(64,Name="fc2",Weights=W("fc2","Weights"),Bias=W("fc2","Bias")) tanhLayer(Name="t2") ...
    fullyConnectedLayer(2,Name="head",Weights=[W3; zeros(size(W3),'single')],Bias=[b3; single(log(std0))])]);
end
function net=qnet(nIn,h)
net=dlnetwork([featureInputLayer(nIn) fullyConnectedLayer(h) reluLayer fullyConnectedLayer(h) reluLayer fullyConnectedLayer(1)]);
end
function [a,lp]=sampleAct(actor,O)
y=forward(actor,O); mu=y(1,:); ls=max(-5,min(1,y(2,:))); sd=exp(ls);
e=randn(size(mu),'single'); u=mu+sd.*e; a=tanh(u);
lp=-0.5*e.^2-ls-0.5*log(2*pi)-log(1-a.^2+1e-6);
end
function [g1,g2]=qLoss2(q1,q2,C,A,y)
l=0.5*mean((forward(q1,[C;A])-y).^2,'all')+0.5*mean((forward(q2,[C;A])-y).^2,'all');
[g1,g2]=dlgradient(l,q1.Learnables,q2.Learnables);
end
function g=qLoss(q,C,A,y)
l=0.5*mean((forward(q,[C;A])-y).^2,'all'); g=dlgradient(l,q.Learnables);
end
function [g,ent]=piLoss(actor,q1,q2,O,C,al,bcW,aRef)
[a,lp]=sampleAct(actor,O); qv=min(forward(q1,[C;a]),forward(q2,[C;a]));
l=mean(al*lp-qv,'all');
if bcW>0
    qs=mean(abs(extractdata(qv)))+1e-6; y=forward(actor,O);
    l=l/qs+bcW*mean((tanh(y(1,:))-aRef).^2,'all');
end
g=dlgradient(l,actor.Learnables); ent=-mean(extractdata(lp));
end
function g=alphaGrad(logA,ent,targetEnt)
l=-logA*single(targetEnt-ent); g=dlgradient(l,logA);
end
function t=soft(t,q,tau)
t.Learnables.Value=cellfun(@(a,b) (1-tau)*a+tau*b,t.Learnables.Value,q.Learnables.Value,'UniformOutput',false);
end
