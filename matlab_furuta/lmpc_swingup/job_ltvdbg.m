here='C:/Capstone1/matlab_furuta/lmpc_swingup'; addpath(here); addpath('C:/Capstone1/matlab_furuta'); addpath('C:/Capstone1/matlab_furuta/swingup_ppo');
D=lm_design(qObs=[200 800],fc=0); dts=[0.01*ones(15,1); 0.05*ones(15,1)];
P=struct('dts',dts,'U0',zeros(numel(dts),1),'w',[10 10 0.3 1],'terminal',10,'r',0.02,'reg',1e-6,'vmax',13.5,'wmax',23);
th=0.05; o=[cos(th);sin(th);0;0;0]; mem=struct();
for it=1:3
 [u,mem,info]=lm_ltv_controller(o,mem,D,P);
 fprintf('iter %d u=%.3f status %d  LQR u=%.3f\n',it,u,info.status,-D.K*[0;th;0;0]);
 fprintf(' plan U(1:8)=%s\n pred th(deg) every 5: %s\n',mat2str(mem.U(1:8)',3),mat2str(rad2deg(info.pred(2,1:5:end)),3));
end
