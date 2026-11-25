c=sp_config; lp=c.p; lp.coulomb=0; [~,~,A,B]=furuta_linearize(lp,false); K=riccati_gain(A,B,diag([10 10 1 1]),1,false);
g=struct('kE',400,'kv',0,'kp',0,'v1',10,'v2',14,'phiClamp',.6,'capAng',deg2rad(20),'capRate',3,'relAng',deg2rad(35));
x0=[0;pi;0;0]; R=sp_rollout(@(o,x,m) sp_expert(x,m,c,K,g),x0,6,c);
th=rad2deg(atan2(sin(squeeze(R.X(2,1,:))),cos(squeeze(R.X(2,1,:)))));
for k=1:20:601, fprintf('t=%.2f th=%.1f w=%.2f v=%.2f u=%.2f\n',R.t(k),th(k),R.X(4,1,k),R.X(3,1,k),R.U(1,min(k,600))); end
