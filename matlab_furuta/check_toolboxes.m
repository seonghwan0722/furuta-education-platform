function has = check_toolboxes
% 설치 정보와 라이선스 기능 이름을 함께 확인한다.
products = ver;
names = ["Control System Toolbox","Reinforcement Learning Toolbox", ...
    "Deep Learning Toolbox","Model Predictive Control Toolbox","Optimization Toolbox"];
features = ["Control_Toolbox","Reinforcement_Learn_Toolbox", ...
    "Neural_Network_Toolbox","MPC_Toolbox","Optimization_Toolbox"];
keys = ["control","rl","deep","mpc","optim"];
installed = ismember(names,string({products.Name}));
licensed = false(size(names));
for k = 1:numel(keys)
    licensed(k) = license('test',char(features(k)));
    has.(keys(k)) = installed(k) && licensed(k);
end
fprintf('MATLAB %s\n',version('-release'));
disp(table(names',installed',licensed',(installed & licensed)', ...
    'VariableNames',{'Toolbox','Installed','Licensed','Available'}))
end
