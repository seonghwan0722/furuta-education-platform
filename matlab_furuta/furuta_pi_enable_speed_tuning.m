function furuta_pi_enable_speed_tuning(mdl)
% Connect the dashboard RPM input to a writable target parameter.
set_param(mdl,'DefaultParameterBehavior','Tunable');
mw = get_param(mdl,'ModelWorkspace');
rpm = getVariable(mw,'motorSpeedRPM');
if ~isa(rpm,'Simulink.Parameter')
    rpm = Simulink.Parameter(rpm);
    rpm.DataType = 'double';
    assignin(mw,'motorSpeedRPM',rpm);
end
mapping = coder.mapping.utils.create(mdl);
setModelParameter(mapping,'motorSpeedRPM','StorageClass','ExportedGlobal');
path = [mdl '/Target RPM input'];
if getSimulinkBlockHandle(path)==-1
    add_block('simulink_hmi_blocks/Edit',path,'Position',[475 8 620 43]);
    set_param([mdl '/Speed reference RPM'],'Position',[480 75 545 105]);
    set_param([mdl '/Speed settings'],'Position',[480 135 545 165]);
end
binding = Simulink.HMI.ParamSourceInfo;
binding.BlockPath = Simulink.BlockPath([mdl '/Speed reference RPM']);
binding.VarName = 'motorSpeedRPM';
binding.WksType = 'model';
set_param(path,'Binding',binding);
end
