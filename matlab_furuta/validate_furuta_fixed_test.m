function validate_furuta_fixed_test(mdl)
% Reject hardware builds using the desktop configuration or default CAN speed.
paths = ["/02 Pi - Sensor and RMD Diagnostics", "/03 Pi - Motor Control and Telemetry"];
enabled = arrayfun(@(p) strcmp(get_param(char(string(mdl)+p),'Commented'),'off'),paths);
if ~any(enabled)
    return
end
assert(nnz(enabled)==1, ...
    'Both Pi subsystems are active. Select one using select_furuta_fixed_test("PiDiagnostics") or select_furuta_fixed_test("PiControl").');
path = [mdl '/03 Pi - Motor Control and Telemetry'];
selector = [path '/Policy shadow enable'];
if enabled(2) && getSimulinkBlockHandle(selector)>0 && ~strcmp(get_param(selector,'Value'),'0')
    assert(strcmp(get_param([path '/Motor CAN transmit'],'Commented'),'on'), ...
        'Pi policy shadow requires Motor CAN transmit to be commented out. Select PiPolicyShadow.');
    workspace = get_param(mdl,'ModelWorkspace');
    assert(isequal(getVariable(workspace,'drive'),zeros(1,4)), ...
        'Pi policy shadow requires drive to be zero. Select PiPolicyShadow.');
end
cfg = getActiveConfigSet(mdl);
assert(strcmp(get_param(cfg,'HardwareBoard'),'Raspberry Pi (64bit)') && ...
    strcmp(get_param(cfg,'Solver'),'FixedStepDiscrete') && str2double(get_param(cfg,'FixedStep'))==.005, ...
    'Active configuration "%s" must use Raspberry Pi (64bit), FixedStepDiscrete, and a 0.005 s fixed step. Reselect the Pi test before building.', cfg.Name);
speed = codertarget.data.getParameterValue(cfg,'CAN.BusSpeed0');
legacySpeed = codertarget.data.getParameterValue(cfg,'CAN.CANBusSpeed');
assert(str2double(string(speed))==1000 && str2double(string(legacySpeed))==1000, ...
    'Furuta Pi CAN must be 1000 kbps. Reselect the Pi test using select_furuta_fixed_test.');
end
