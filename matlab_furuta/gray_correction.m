function a = gray_correction(net,x,u)
% 각도는 주기적 표현을 쓰고 속도와 가속도 크기를 정규화한다.
z = [x(1,:)/pi; cos(x(2,:));sin(x(2,:));x(3:4,:)/20;u];
a = 100*stripdims(forward(net,dlarray(single(z),'CB')));
end
