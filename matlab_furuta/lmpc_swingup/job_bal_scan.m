root='C:/Capstone1/matlab_furuta'; addpath(root); addpath([root '/lmpc_swingup']); addpath([root '/swingup_ppo']); addpath([root '/rev11']);
cp=rev11_ident_config(); L=load([root '/rev11/rev11_design.mat']); g=L.g;
x0=[zeros(1,4); deg2rad([2 -2 4 -4]); zeros(2,4)];
evs={struct('stic',0.5,'biasDeg',1,'coulTh',1e-3), struct('stic',0.5,'biasDeg',-1,'coulTh',2e-3)};
res=[];
for Qa=[10 3]
 for Qw=[1 5 20]
  for Qv=[1 5]
   for Rr=[1 3]
    D=lm_design(qObs=[200 800],fc=0,vmax=13.5,plantCfg=cp,Q=[Qa 10 Qv Qw],R=Rr);
    S=[];
    for e=1:2
      ev=struct('filter',true,'delay',1,'armLim',15,'pendLim',25,'frac',0,'plantCfg',cp); f=fieldnames(evs{e}); for q=1:numel(f), ev.(f{q})=evs{e}.(f{q}); end
      [~,R]=lm_eval(D,g,x0,20,ev); S=[S; bal_metric(R,4)]; %#ok<AGROW>
    end
    fprintf('SCAN Q=[%g 10 %g %g] R=%g: minLongest %.2f, mean std th %.2f, max th %.2f, |w|>0.5 %.3f, flips %.0f\n',Qa,Qv,Qw,Rr,min(S(:,1)),mean(S(:,3)),max(S(:,5)),mean(S(:,2)),mean(S(:,4)));
   end
  end
 end
end
