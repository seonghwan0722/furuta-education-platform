c=sp_config; lp=c.p; lp.coulomb=0;
[~,~,A,B]=furuta_linearize(lp,false);
K=riccati_gain(A,B,diag([10 10 1 1]),1,false); disp(K)
starts=deg2rad([180 -180 179.9 175 -175 170 -170 160 -160 150 -150 140]);
x0=[zeros(1,numel(starts)); starts; zeros(2,numel(starts))];
for Erest=[0.001 0.003 0.006]
for v1=[10]
 for kE=[150 247 400]
  g=struct('kE',kE,'kv',0.0,'kp',0,'v1',v1,'v2',14,'phiClamp',.6,'capAng',deg2rad(20),'capRate',3,'relAng',deg2rad(35),'Erest',Erest);
  R=sp_rollout(@(o,x,m) sp_expert(x,m,c,K,g),x0,25,c);
  M=sp_metrics(R,c,15,25);
  fprintf('Er=%g v1=%g kE=%g pass %d/%d  maxArm %.2f maxPend %.2f reach %s\n',Erest,v1,kE,nnz(M.Passed),height(M),max(M.PeakArmRate),max(M.PeakPendRate),mat2str(M.ReachTime',3));
 end
end
end
