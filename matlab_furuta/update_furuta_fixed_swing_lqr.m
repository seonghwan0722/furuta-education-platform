function update_furuta_fixed_swing_lqr
% Add the agreed capture gate inside the existing LQR subsystem.
folder = fileparts(mfilename('fullpath'));
m = 'furuta_block_model_fixed';
file = fullfile(folder,[m '.slx']);
load_system(file);
assert(strcmp(get_param(m,'Dirty'),'off'),'Save open model edits before updating.');
backup = fullfile(folder,[m '.before_swing_lqr.slx.bak']);
if ~isfile(backup), copyfile(file,backup); end
s = [m '/01 MIL - Controller and Plant/03 Controllers/LQR'];
w = get_param(m,'ModelWorkspace');
assignin(w,'swingLqrThresholds',[deg2rad(13) .2 deg2rad(30)]);
if getSimulinkBlockHandle([s '/Swing-up to LQR'])<0
    load_system('simulink');
    add_block('simulink/User-Defined Functions/MATLAB Function',[s '/Swing-up to LQR'], ...
        'Position',[430 95 575 205]);
    r = sfroot;
    chart = r.find('-isa','Stateflow.EMChart','Path',[s '/Swing-up to LQR']);
    chart.Script = sprintf(['function [u,balancing] = control(x,lqr,mode,thresholds,p)\n' ...
        '[u,balancing] = furuta_swing_lqr_step(x,lqr,mode==1,thresholds,p);\nend']);
    add_block('simulink/Sources/Constant',[s '/Capture thresholds'], ...
        'Value','swingLqrThresholds','Position',[170 230 300 260]);
    add_block('simulink/Sources/Constant',[s '/Energy parameters'], ...
        'Value','plantCoefficients','Position',[170 290 300 320]);
    add_block('simulink/Sinks/To Workspace',[s '/LQR active log'], ...
        'VariableName','swingLqrActive','SaveFormat','Timeseries','Position',[635 220 750 250]);
    output = get_param([s '/u'],'PortHandles');
    source = get_param(get_param(output.Inport,'Line'),'SrcPortHandle');
    delete_line(s,source,output.Inport);
    p = get_param([s '/Swing-up to LQR'],'PortHandles');
    add_line(s,source,p.Inport(2),'autorouting','on');
    add_line(s,'x/1','Swing-up to LQR/1','autorouting','on');
    add_line(s,'mode/1','Swing-up to LQR/3','autorouting','on');
    add_line(s,'Capture thresholds/1','Swing-up to LQR/4','autorouting','on');
    add_line(s,'Energy parameters/1','Swing-up to LQR/5','autorouting','on');
    add_line(s,p.Outport(1),output.Inport,'autorouting','on');
    add_line(s,'Swing-up to LQR/2','LQR active log/1','autorouting','on');
end
save_system(m,file);
fprintf('SAVED capture angle=13 deg, pendulum rate=0.2 rad/s, release angle=30 deg\n');
end
