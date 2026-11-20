% Sensitivity of wrapped RL controllers to a residual pendulum zero error (true trim != 2.77 deg)
root='C:/Capstone1/matlab_furuta'; addpath(root); addpath([root '/swingup_ppo']); addpath([root '/rev11']); addpath([root '/swingup_ppo/pi_wrappers']);
c=rev11_ident_config(); if ~exist('fns','var'), fns=["furuta_ppo_rev11_step","furuta_sac_rev11_step"]; end
for fn=fns
  f=str2func(fn);
  for b=[-2 -1 0 1 2]
    res=[];
    for th0=deg2rad([180 175 -175 178 -178])
      s=sp_env2.reset([0;th0;0;0],c,struct('filter',true,'delayMax',1,'fracMax',0,'alpha',0,'coul',0,'eta',0,'regenBudget',0.8));
      clear(char(fn)); N=2000; th=zeros(1,N); w=th; v=th;
      for k=1:N
        [o,s]=sp_env2.observe(s,c.Ts);
        xm=[o(3); atan2(o(2),o(1))+deg2rad(2.77+b); o(4); o(5)];
        u=f(xm,true); s=sp_env2.step(s,u,c);
        th(k)=atan2(sin(s.x(2)),cos(s.x(2))); w(k)=s.x(4); v(k)=s.x(3);
      end
      ok=abs(th)<deg2rad(5)&abs(w)<0.5; best=0; cc=0; for j=1:N, if ok(j), cc=cc+1; best=max(best,cc); else, cc=0; end, end
      res(end+1,:)=[best*c.Ts, max(abs(v(end-500:end)))]; %#ok<AGROW>
    end
    fprintf('BIAS %s bias %+d deg: longest hold %s s, late max|v| %s\n',fn,b,mat2str(round(res(:,1)'*10)/10),mat2str(round(res(:,2)'*10)/10));
  end
end
