function compare_furuta_actuators
% Copy the existing actuator subsystems into one common-input PC test harness.
folder=fileparts(mfilename('fullpath'));
light='furuta_rl_training'; fixed='furuta_block_model_fixed';
load_system(fullfile(folder,[light '.slx']));
load_system(fullfile(folder,[fixed '.slx']));
harness='furuta_actuator_comparison';
assert(~bdIsLoaded(harness),'Close the actuator comparison harness before rerunning.');
new_system(harness);
cleanup=onCleanup(@() finish({harness,light,fixed}));
fw=get_param(fixed,'ModelWorkspace');
lw=get_param(light,'ModelWorkspace');
w=get_param(harness,'ModelWorkspace');
parameters=struct('rmd',getVariable(fw,'rmd'), ...
    'driveElectrical',getVariable(fw,'driveElectrical'), ...
    'controlPeriod',getVariable(fw,'controlPeriod'), ...
    'rmdCommandDelaySamples',getVariable(lw,'rmdCommandDelaySamples'), ...
    'rmdCurrentTimeConstant',getVariable(lw,'rmdCurrentTimeConstant'));
parameters.maxTorque=1.5*parameters.rmd.Kt;
for name=string(fieldnames(parameters))', assignin(w,name,parameters.(name)); end
set_param(harness,'SolverType','Fixed-step','Solver','ode14x', ...
    'FixedStep','driveElectrical.sampleTime','EnableMultiTasking','off', ...
    'StopTime','2','ReturnWorkspaceOutputs','on');
load_system('simulink');
sources={ [light '/04 Actuator/RMD X6 P20 60 E'], ...
    [fixed '/01 MIL - Controller and Plant/04 Actuator/RMD X6 P20 60 E']};
labels=["Light","Fixed"];
for k=1:2
    path=[harness '/' char(labels(k)) ' actuator'];
    add_block(sources{k},path,'Position',[300 100+150*(k-1) 550 190+150*(k-1)]);
    logs=find_system(path,'BlockType','ToWorkspace');
    for i=1:numel(logs)
        set_param(logs{i},'SaveFormat','Timeseries', ...
            'VariableName',[lower(char(labels(k))) '_' get_param(logs{i},'VariableName')]);
    end
    inputs=find_system(path,'SearchDepth',1,'BlockType','Inport');
    ports=get_param(path,'PortHandles');
    for i=1:numel(inputs)
        index=str2double(get_param(inputs{i},'Port'));
        name=get_param(inputs{i},'Name');
        if strcmp(name,'Requested torque')
            torquePort(k)=ports.Inport(index); %#ok<AGROW>
        elseif strcmp(name,'Output shaft speed')
            speedPort=ports.Inport(index);
            add_block('simulink/Sources/Constant',[harness '/Shaft speed'], ...
                'Value','shaftSpeed','Position',[50 330 160 360]);
            speedSource=get_param([harness '/Shaft speed'],'PortHandles');
            add_line(harness,speedSource.Outport,speedPort,'autorouting','on');
        else
            error('Unexpected actuator input %s.',name);
        end
    end
    log=[harness '/' char(labels(k)) ' torque'];
    add_block('simulink/Sinks/To Workspace',log,'SaveFormat','Timeseries', ...
        'VariableName',['comparison' char(labels(k)) 'Torque'], ...
        'Position',[650 130+150*(k-1) 800 160+150*(k-1)]);
    logPorts=get_param(log,'PortHandles');
    add_line(harness,ports.Outport(1),logPorts.Inport,'autorouting','on');
end
add_block('simulink/Sources/From Workspace',[harness '/Requested torque'], ...
    'VariableName','requestedTorque','Interpolate','off', ...
    'OutputAfterFinalValue','Holding final value','Position',[30 130 190 160]);
source=get_param([harness '/Requested torque'],'PortHandles');
for k=1:2, add_line(harness,source.Outport,torquePort(k),'autorouting','on'); end
times=[0 .05 .10 .15 .20 .35 .55 .80 1.05 1.30 1.55 1.80 2]';
amps=[0 .004 .006 .014 .016 .1 .5 1.5 -1.5 1.8 -1.8 0 0]';
assignin(w,'requestedTorque',[times amps*parameters.rmd.Kt]);
assignin(w,'shaftSpeed',0);
output=fullfile(folder,'results',['actuator_comparison_' char(datetime('now','Format','yyyyMMdd_HHmmss'))]);
mkdir(output);
save_system(harness,fullfile(output,[harness '.slx']));
speeds=[0 10 20 -20]; runs={}; metrics=[]; segments=[];
for k=1:numel(speeds)
    in=Simulink.SimulationInput(harness);
    in=in.setVariable('shaftSpeed',speeds(k),Workspace=harness);
    out=sim(in);
    time=(0:parameters.driveElectrical.sampleTime:2)';
    li=sample(out.light_rmdCurrentTrace,time);
    fi=sample(out.fixed_rmdCurrentTrace,time);
    lt=sample(out.comparisonLightTorque,time);
    ft=sample(out.comparisonFixedTorque,time);
    reference=sample(out.fixed_driverCurrentRefTrace,time);
    voltage=sample(out.fixed_driverVoltageTrace,time);
    duty=sample(out.fixed_driverDutyTrace,time);
    metrics(end+1,:)=[speeds(k) sqrt(mean((fi-li).^2)) max(abs(fi-li)) ...
        sqrt(mean((ft-lt).^2)) max(abs(ft-lt)) max(abs(fi)) max(abs(voltage))]; %#ok<AGROW>
    for j=1:numel(times)-1
        duration=times(j+1)-times(j);
        mask=time>=times(j+1)-min(.03,duration/3) & time<times(j+1);
        expected=round(amps(j)/parameters.rmd.currentLSB)*parameters.rmd.currentLSB;
        expected=max(-1.5,min(1.5,expected));
        segments(end+1,:)=[speeds(k) times(j) amps(j) expected mean(reference(mask)) ...
            mean(li(mask)) mean(fi(mask)) mean(lt(mask)) mean(ft(mask)) ...
            sqrt(mean((fi(mask)-li(mask)).^2))]; %#ok<AGROW>
    end
    runs{k}=struct('shaftSpeed',speeds(k),'time',time,'lightCurrent',li,'fixedCurrent',fi, ...
        'lightTorque',lt,'fixedTorque',ft,'currentReference',reference,'voltage',voltage,'duty',duty);
    save(fullfile(output,'progress.mat'),'runs','parameters','metrics','segments','times','amps');
    fprintf('ACTUATOR speed=%g current_RMSE=%.6f A torque_RMSE=%.6f Nm peak_current=%.6f A\n', ...
        speeds(k),metrics(end,2),metrics(end,4),metrics(end,6));
end
report=array2table(metrics,'VariableNames',{'ShaftSpeedRadS','CurrentRMSEA','PeakCurrentDifferenceA', ...
    'TorqueRMSENm','PeakTorqueDifferenceNm','FixedPeakCurrentA','FixedPeakVoltageV'});
segmentReport=array2table(segments,'VariableNames',{'ShaftSpeedRadS','StepTime', ...
    'RequestedCurrentA','ExpectedLimitedCurrentA','FixedReferenceA','LightCurrentA', ...
    'FixedCurrentA','LightTorqueNm','FixedTorqueNm','SteadyCurrentDifferenceRMSEA'});
writetable(report,fullfile(output,'summary.csv'));
writetable(segmentReport,fullfile(output,'step_plateaus.csv'));
save(fullfile(output,'responses.mat'),'runs','report','segmentReport','parameters','times','amps');
f=figure('Visible','off','Position',[100 100 1400 950]); tiledlayout(3,4);
for k=1:numel(runs)
    z=runs{k};
    nexttile(k); plot(z.time,[z.lightCurrent z.fixedCurrent]); grid on;
    title(sprintf('Shaft speed %g rad/s',z.shaftSpeed)); ylabel('Current (A)');
    if k==1, legend('Light model','Fixed electrical','Location','best'); end
    nexttile(4+k); plot(z.time,[z.lightTorque z.fixedTorque]); grid on; ylabel('Torque (Nm)');
    nexttile(8+k); plot(z.time,z.fixedCurrent-z.lightCurrent); grid on;
    ylabel('Current difference (A)'); xlabel('Time (s)');
end
exportgraphics(f,fullfile(output,'responses.png'),'Resolution',150); close(f);
disp(report); fprintf('ACTUATOR_COMPARISON_RESULTS %s\n',output);
end

function values=sample(series,time)
values=interp1(series.Time,squeeze(series.Data),time,'previous','extrap');
values=values(:);
end

function finish(models)
for k=1:numel(models)
    if bdIsLoaded(models{k}), close_system(models{k},0); end
end
end
