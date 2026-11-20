function furuta_pi_enable_current_tuning(mdl)
% Connect a dashboard input to the manual current reference (A) so it can be
% changed while the Pi app runs (Monitor & Tune). Limits still clamp it.
set_param(mdl,'DefaultParameterBehavior','Tunable');
mw = get_param(mdl,'ModelWorkspace');
iq = getVariable(mw,'manualCurrentA');
if ~isa(iq,'Simulink.Parameter')
    iq = Simulink.Parameter(iq);
    iq.DataType = 'double';
    assignin(mw,'manualCurrentA',iq);
end
mapping = coder.mapping.utils.create(mdl);
setModelParameter(mapping,'manualCurrentA','StorageClass','ExportedGlobal');
path = [mdl '/Current input A'];
if getSimulinkBlockHandle(path)==-1
    add_block('simulink_hmi_blocks/Edit',path,'Position',[475 -40 620 -5]);
end
binding = Simulink.HMI.ParamSourceInfo;
binding.BlockPath = Simulink.BlockPath([mdl '/Current reference A']);
binding.VarName = 'manualCurrentA';
binding.WksType = 'model';
set_param(path,'Binding',binding);
end
