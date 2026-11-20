function r = run_scenario_simulink(controller,scenario)
% 빈 제어기([])는 모델 내부 LQR Gain을 사용한다.
model = 'furuta_block_model';
if ~bdIsLoaded(model)
    build_furuta_simulink;
end
assert(round(scenario.p.Ts/scenario.p.h)==5, ...
    '블록 플랜트는 제어 주기당 RK4 서브스텝이 5개입니다.');
[t,signals,workspaceData] = scenario_inputs(scenario);
furuta_sl_context([],[],controller,scenario);
cleanup = onCleanup(@() furuta_sl_context());
in = Simulink.SimulationInput(model);
in = in.setVariable('scenarioStimulus',workspaceData,Workspace=model);
in = in.setVariable('initialState',scenario.x0,Workspace=model);
in = in.setVariable('controlPeriod',scenario.p.Ts,Workspace=model);
in = in.setVariable('integrationStep',scenario.p.h,Workspace=model);
in = in.setVariable('plantCoefficients',furuta_block_coefficients(scenario.p),Workspace=model);
in = in.setVariable('maxTorque',scenario.p.tau_max,Workspace=model);
in = in.setVariable('usePolicyCallback',double(~isempty(controller)),Workspace=model);
in = in.setModelParameter('StopTime',num2str(t(end),17),'SimulationMode','normal');
out = sim(in);
n = numel(t)-1;
if ismatrix(out.stateTrace)
    x = out.stateTrace';
else
    x = reshape(out.stateTrace,4,[]);
end
raw = out.commandTrace';
action = out.actionTrace';
elapsed = out.computeTrace';
assert(isequal(size(x),[4 n+1]) && numel(raw)==n+1 ...
    && numel(action)==n+1 && numel(elapsed)==n+1, ...
    'Simulink 기록의 샘플 수가 예상과 다릅니다.');
u = action(1:n);
u(~isfinite(raw(1:n))) = NaN;
bad = find(isnan(u) | any(~isfinite(x(:,2:end)) | abs(x(:,2:end))>1e4,1),1);
if ~isempty(bad)
    x(:,bad+1:end) = NaN;
    u(bad+1:end) = NaN;
    elapsed(bad+1:n) = NaN;
end
r = scenario_result(scenario,t,x,u,signals(3,1:n),elapsed(1:n));
end
