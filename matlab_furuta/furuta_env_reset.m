function [obs,info] = furuta_env_reset
% 정확히 아래 자세에서 시작한다.
info.x = [0;pi;0;0];
info.pendingAction = 0;
obs = furuta_obs(info.x);
end
