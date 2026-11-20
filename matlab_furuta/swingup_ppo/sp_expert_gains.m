function [K,g] = sp_expert_gains(c)
lp=c.p; lp.coulomb=0; [~,~,A,B]=furuta_linearize(lp,false);
K=riccati_gain(A,B,diag([10 10 1 1]),1,false);
g=struct('kE',400,'kv',0,'kp',0,'v1',10,'v2',14,'phiClamp',.6,'capAng',deg2rad(20), ...
    'capRate',3,'relAng',deg2rad(35),'Erest',0.001);
end
