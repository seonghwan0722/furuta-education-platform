function [obs,r,done,info] = furuta_env_step(u,info,p,level)
% PPO의 가우시안 출력도 실제 액추에이터 범위로 제한한다.
u = max(-1,min(1,u));
assert(abs(p.Ts-.01)<1e-10,'The function environment uses a one-step 10 ms action delay.');
if ~isfield(info,'pendingAction'), info.pendingAction=0; end
applied=info.pendingAction;
info.pendingAction=u;
info.appliedAction=applied;
info.x = furuta_step(info.x,applied,p);
obs = furuta_obs(info.x);
[r,done] = furuta_reward(info.x,applied,level);
end
