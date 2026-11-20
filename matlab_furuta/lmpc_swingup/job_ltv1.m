here='C:/Capstone1/matlab_furuta/lmpc_swingup'; addpath(here); addpath('C:/Capstone1/matlab_furuta'); addpath('C:/Capstone1/matlab_furuta/swingup_ppo');
D=lm_design(qObs=[200 800],fc=0);
dts=[0.01*ones(5,1); 0.05*ones(25,1)];
P=struct('dts',dts,'U0',zeros(numel(dts),1)+0.05,'w',[3 1 0.05 0.5],'terminal',3,'r',0.02,'reg',1e-6,'vmax',13.5);
st=deg2rad([180 175 -175]); x0=[zeros(1,3); st; zeros(2,3)];
[M,R,ts]=lm_ltv_eval(D,P,x0,8,struct('filter',true,'delay',1,'armLim',15,'pendLim',25,'frac',0));
disp(M(:,[1 2 3 5 6 8 9 10])); fprintf('step time %.2f ms\n',ts*1e3);
for j=1:3, th=rad2deg(atan2(sin(squeeze(R.X(2,j,:))),cos(squeeze(R.X(2,j,:))))); fprintf('start %d: min|th| %.1f, |th| at 2,4,6,8 s: %s\n',j,min(abs(th)),mat2str(abs(th([201 401 601 801]))',3)); end
