function mdl = select_furuta_fixed_test(mode)
% Activate a single test and its matching configuration in the combined model.
arguments
    mode (1,1) string {mustBeMember(mode,["MIL","PiDiagnostics","PiControl","PiPolicyShadow","SelfTest"])}
end
mdl = 'furuta_block_model_fixed';
if ~bdIsLoaded(mdl)
    load_system(fullfile(fileparts(mfilename('fullpath')),[mdl '.slx']));
end
assert(strcmp(get_param(mdl,'SimulationStatus'),'stopped'),'Stop the model before switching tests.');
modes = ["MIL","PiDiagnostics","PiControl","SelfTest"];
names = ["01 MIL - Controller and Plant","02 Pi - Sensor and RMD Diagnostics", ...
    "03 Pi - Motor Control and Telemetry","04 PC - Functional Self-Test"];
configs = ["Furuta Desktop","Furuta Pi","Furuta Pi","Furuta Self-Test"];
shadow = mode=="PiPolicyShadow";
if shadow
    active = find(modes=="PiControl");
else
    active = find(modes==mode);
end
motor = [mdl '/03 Pi - Motor Control and Telemetry/Motor CAN transmit'];
selector = [mdl '/03 Pi - Motor Control and Telemetry/Policy shadow enable'];
if getSimulinkBlockHandle(selector)>0
    wasShadow = strcmp(get_param(selector,'Value'),'1');
    workspace = get_param(mdl,'ModelWorkspace');
    if shadow
        if ~wasShadow
            prior = struct('MotorComment',get_param(motor,'Commented'), ...
                'Drive',getVariable(workspace,'drive'));
            set_param(selector,'UserData',prior,'UserDataPersistent','on');
        end
        assignin(workspace,'drive',zeros(1,4));
        set_param(motor,'Commented','on');
        set_param(selector,'Value','1');
    else
        if wasShadow
            prior = get_param(selector,'UserData');
            set_param(motor,'Commented',prior.MotorComment);
            assignin(workspace,'drive',prior.Drive);
        end
        set_param(selector,'Value','0');
    end
else
    assert(~shadow,'Run update_furuta_fixed_shadow before selecting PiPolicyShadow.');
end
setActiveConfigSet(mdl,char(configs(active)));
if configs(active)=="Furuta Pi"
    cfg = getActiveConfigSet(mdl);
    codertarget.data.setParameterValue(cfg,'CAN.BusSpeed0','1000');
    codertarget.data.setParameterValue(cfg,'CAN.CANBusSpeed','1000');
end
for k=1:numel(names)
    path = [mdl '/' char(names(k))];
    if k==active
        set_param(path,'Commented','off');
    else
        set_param(path,'Commented','on');
    end
end
end
