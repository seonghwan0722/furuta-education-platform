function [r,done] = furuta_reward(x,u,level)
% 실제 실패만 종료하며 시간 제한은 학습 옵션에서 처리한다.
r = cos(x(2))-0.01*u^2;
if level == 2
    r = r-0.001*x(4)^2-0.00002*x(3)^2+(abs(wrap_theta(x(2)))<0.35);
end
done = abs(x(1))>2*pi;
if done
    r = -50;
end
end
