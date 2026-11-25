root='C:/Capstone1/matlab_furuta'; addpath(root); addpath([root '/lmpc_swingup']); addpath([root '/swingup_ppo']); addpath([root '/rev11']);
B=load([root '/rev11/rev11_design_b.mat']); cp=B.cp;
x0=[zeros(1,4); deg2rad([180 175 -175 178]); zeros(2,4)];
evs={struct('stic',0.5,'biasDeg',1,'coulTh',1e-3), struct('stic',1.0,'biasDeg',-1,'coulTh',2e-3), struct('stic',0.5,'biasDeg',0,'coulTh',1e-3,'frac',0.5)};
for Rr=[1 3]
 for qo={[200 800],[50 200]}
  D=lm_design(qObs=qo{1},fc=0,vmax=13.5,plantCfg=cp,Q=[3 10 5 5],R=Rr);
  for sb=[Inf 0.3 0.15]
   g=B.g; g.balance="lmpc"; g.slewBal=sb; S=[]; P=0;
   for e=1:3
     ev=struct('filter',true,'delay',1,'armLim',15,'pendLim',25,'frac',0,'plantCfg',cp); f=fieldnames(evs{e}); for q=1:numel(f), ev.(f{q})=evs{e}.(f{q}); end
     [M,R]=lm_eval(D,g,x0,20,ev); S=[S; bal_metric(R,6)]; P=P+nnz(M.Passed); %#ok<AGROW>
     sat(e)=mean(abs(R.U(:,601:end))>=0.99,'all'); %#ok<SAGROW>
   end
   fprintf('CHAT R=%g qObs=%s slewBal=%g: pass %d/12 strict>=5s %d/12 meanStd %.2f flips %.0f sat %.3f\n',Rr,mat2str(qo{1}),sb,P,nnz(S(:,1)>=5),mean(S(:,3)),mean(S(:,4)),mean(sat));
  end
 end
end
