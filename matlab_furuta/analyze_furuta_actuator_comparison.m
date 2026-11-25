function analyze_furuta_actuator_comparison(folder)
% Quantify latency and document the manufacturer's unit conversion.
d=load(fullfile(folder,'responses.mat'));
z=d.runs{1}; t=z.time; period=d.parameters.controlPeriod;
start=.8; baseline=.5; target=1.5;
within=t>=start & t<1.05;
indices=find(within);
values=(z.fixedCurrent(indices)-baseline)/(target-baseline);
at10=indices(find(values>=.1,1)); at90=indices(find(values>=.9,1));
torque=(z.fixedTorque(indices)/d.parameters.rmd.Kt-baseline)/(target-baseline);
torque10=indices(find(torque>=.1,1)); torque90=indices(find(torque>=.9,1));
delays=[];
for run=1:2
    q=d.runs{run};
    for delay=0:.001:2*period
        shifted=interp1(q.time,q.lightTorque,max(0,q.time-delay),'previous');
        delays(end+1,:)=[q.shaftSpeed delay sqrt(mean((q.fixedTorque-shifted).^2))]; %#ok<AGROW>
    end
end
delayReport=array2table(delays,'VariableNames',{'ShaftSpeedRadS','DelaySeconds','TorqueRMSENm'});
writetable(delayReport,fullfile(folder,'delay_fit.csv'));
gear=d.parameters.rmd.gearRatio;
keBus=16*gear*60/(2*pi*1000);
kePhase=keBus/sqrt(3);
vmax=d.parameters.rmd.voltage/sqrt(3);
speedZero=vmax/d.parameters.driveElectrical.Ke;
speedAtCap=(vmax-d.parameters.driveElectrical.R*1.5)/d.parameters.driveElectrical.Ke;
audit=struct('sourceKeVdcPerKrpm',16,'gearRatio',gear, ...
    'outputKeBusVsPerRad',keBus,'outputKePhasePeakVsPerRad',kePhase, ...
    'modelKe',d.parameters.driveElectrical.Ke,'phasePeakVoltageLimitV',vmax, ...
    'zeroCurrentVoltageBoundaryRadS',speedZero,'at1p5ACurrentVoltageBoundaryRadS',speedAtCap, ...
    'fixedCurrent10PercentDelaySeconds',t(at10)-start, ...
    'fixedCurrent90PercentDelaySeconds',t(at90)-start, ...
    'fixedTorque10PercentDelaySeconds',t(torque10)-start, ...
    'fixedTorque90PercentDelaySeconds',t(torque90)-start);
save(fullfile(folder,'analysis.mat'),'audit','delayReport');
fid=fopen(fullfile(folder,'unit_audit.json'),'w');
fprintf(fid,'%s',jsonencode(audit,PrettyPrint=true)); fclose(fid);
f=figure('Visible','off','Position',[100 100 1100 650]); tiledlayout(2,1);
nexttile; plot(t,[z.lightCurrent z.fixedCurrent]); xlim([.795 .825]); grid on;
ylabel('Current (A)'); legend('Light','Fixed electrical');
nexttile; plot(t,[z.lightTorque z.fixedTorque]); xlim([.795 .825]); grid on;
ylabel('Torque (Nm)'); xlabel('Time (s)');
exportgraphics(f,fullfile(folder,'step_latency.png'),'Resolution',150); close(f);
disp(audit); disp(delayReport);
end
