function y = furuta_obs(x)
% 관측 순서는 환경과 정책 평가에서 동일하다.
y = [cos(x(2)); sin(x(2)); x([1 3 4])];
end
