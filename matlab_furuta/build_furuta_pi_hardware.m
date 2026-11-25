function file = build_furuta_pi_hardware(opts)
% Create a Raspberry Pi deployment model with a separately gated RMD CAN transmit.
arguments
    opts.Checkpoint (1,1) string = ""
    opts.CurriculumPolicy (1,1) logical = false
    % Plain-MATLAB policy function name (e.g. furuta_swingup_policy, written by
    % swingup_ppo/sp_export_infer). Takes the 5x1 Pi observation, returns the action.
    opts.PolicyFunction (1,1) string = ""
    % Stateful classical controller function [u,balancing]=f(x,active) (e.g. furuta_lqr_step,
    % furuta_pid_step, furuta_lmpc_step from lmpc_swingup/lm_export_step). x=[arm;pend;arm rate;pend rate].
    % It is called only on actuation (10 ms) ticks with a fresh valid sample; no checkpoint needed.
    opts.ControllerFunction (1,1) string = ""
    opts.DriveProfile (1,1) string = ""
    opts.Folder (1,1) string = string(fileparts(mfilename('fullpath')))
    opts.I2CBoard (1,1) string = "Pi 5 Model"
    opts.Verification (1,1) logical = false
    opts.ManualCurrent (1,1) logical = false
    opts.CurrentA (1,1) double {mustBeFinite} = 0
    opts.SpeedControl (1,1) logical = false
    opts.NativeSpeed (1,1) logical = false
    opts.SpeedRPM (1,1) double {mustBeFinite} = 0
    opts.AutoArmHome (1,1) logical = true   % first valid 0x92 angle of each run = arm zero
    % Consecutive missed (invalid / un-acked) samples tolerated with a 0 A command before Motor Off
    % latches (user decision 2026-11-20). 0 = original behaviour (first miss latches).
    opts.TimingLog (1,1) logical = false   % log Pi wall-clock step timing as furutaPiTiming (diagnostic, 2026-11-22)
    opts.MissTolerance (1,1) double {mustBeInteger,mustBeNonnegative,mustBeLessThanOrEqual(opts.MissTolerance,2)} = 0
end
root = fileparts(mfilename('fullpath'));
profile = jsondecode(fileread(fullfile(root,'..','deployment','pi','rmd_x6_48v.json')));
armed = strlength(opts.DriveProfile)>0;
drive = [0 0 0 0];
limits = zeros(1,4);
if ~armed && ~opts.Verification
    defaults = jsondecode(fileread(fullfile(root,'..','deployment','pi','rmd_speed_drive_candidate.json')));
    limits(3) = defaults.limits(3);
end
mdl = 'furuta_pi_hardware';
assert(~opts.ManualCurrent || (~opts.Verification && strlength(opts.Checkpoint)==0), ...
    'Manual current mode uses its own reference.');
assert(opts.ManualCurrent || opts.CurrentA==0,'CurrentA requires ManualCurrent=true.');
assert(abs(opts.CurrentA)<=327.67,'Current reference must fit the RMD command field.');
assert(~opts.SpeedControl || (~opts.ManualCurrent && ~opts.Verification && strlength(opts.Checkpoint)==0), ...
    'Speed control uses its own RPM reference.');
assert(opts.SpeedControl || opts.SpeedRPM==0,'SpeedRPM requires SpeedControl=true.');
assert((~opts.CurriculumPolicy && strlength(opts.PolicyFunction)==0) || strlength(opts.Checkpoint)>0, ...
    'CurriculumPolicy requires a PPO checkpoint.');
assert(~opts.NativeSpeed || opts.SpeedControl,'NativeSpeed requires SpeedControl=true.');
if opts.Verification
    assert(~armed && strlength(opts.Checkpoint)==0,'Verification sends read requests only.');
    mdl = 'furuta_pi_hardware_verify';
elseif armed
    mdl = 'furuta_pi_hardware_drive';
    d = jsondecode(fileread(opts.DriveProfile));
    assert(d.watchdog_cutoff_verified && d.hardware_enable_cutoff_verified && ...
        abs(d.current_sign)==1 && isfinite(d.amps_per_action) && d.amps_per_action>=.01 && ...
        isfinite(d.max_current_a) && d.max_current_a>=.01 && d.max_current_a<=d.amps_per_action && ...
        isfinite(d.drive_seconds) && d.drive_seconds>.1 && d.drive_seconds<=20 && ...   % 20 s cap: user request 2026-11-20
        numel(d.limits)==4 && all(isfinite(d.limits)) && all(d.limits>0) && ...
        (opts.ManualCurrent || opts.SpeedControl || strlength(opts.Checkpoint)>0 || strlength(opts.ControllerFunction)>0), ...
        'Verified drive profile and command source required.');
    drive = [d.current_sign d.amps_per_action d.max_current_a d.drive_seconds];
    limits = d.limits(:).';
    % Explicit user-set flags (JSON has no Inf): no drive expiry / no arm-angle trip.
    % Speed, pendulum, sensor and CAN-ack interlocks and the watchdog stay active.
    if isfield(d,'drive_seconds_unlimited') && isequal(d.drive_seconds_unlimited,true)
        drive(4) = Inf;
    end
    if isfield(d,'arm_angle_unlimited') && isequal(d.arm_angle_unlimited,true)
        limits(1) = Inf;
    end
elseif strlength(opts.Checkpoint)>0
    mdl = 'furuta_pi_hardware_policy';
elseif strlength(opts.ControllerFunction)>0
    mdl = 'furuta_pi_hardware_controller';
end
assert(strlength(opts.ControllerFunction)==0 || (strlength(opts.Checkpoint)==0 && ...
    ~opts.ManualCurrent && ~opts.SpeedControl && ~opts.Verification), ...
    'ControllerFunction is a separate command source.');
if opts.ManualCurrent
    mdl = 'furuta_pi_motor_output';
    if armed
        mdl = 'furuta_pi_motor_output_drive';
        assert(opts.CurrentA~=0,'Provide an explicit nonzero reference for an armed current test.');
    end
end
speedSettings = [0 Inf];
if opts.SpeedControl
    mdl = 'furuta_pi_motor_speed';
    if opts.NativeSpeed
        mdl = 'furuta_pi_motor_speed_a2';
        if armed
            mdl = 'furuta_pi_motor_speed_a2_drive';
            assert(isfield(d,'a2_current_cap_verified') && isequal(d.a2_current_cap_verified,true), ...
                'Verify the RMD A2 current cap on this drive before enabling native speed.');
            assert(isscalar(d.a2_rated_current_a) && isfinite(d.a2_rated_current_a) && d.a2_rated_current_a>0 && ...
                isscalar(d.a2_current_percent) && isfinite(d.a2_current_percent) && ...
                d.a2_current_percent==fix(d.a2_current_percent) && d.a2_current_percent>=1 && ...
                d.a2_current_percent<=255 && d.a2_rated_current_a*d.a2_current_percent/100<=drive(3), ...
                'The nonzero A2 percentage must stay within the verified current limit.');
            assert(isscalar(d.max_target_rpm) && isfinite(d.max_target_rpm) && d.max_target_rpm>0 && ...
                d.max_target_rpm*2*pi/60<limits(3) && d.max_target_rpm<=double(intmax('int32'))/600 && ...
                abs(opts.SpeedRPM)<=d.max_target_rpm,'Verify the A2 speed reference limit.');
            speedSettings = [d.a2_current_percent d.max_target_rpm];
        end
    elseif armed
        mdl = 'furuta_pi_motor_speed_drive';
        assert(isscalar(d.speed_kp_a_per_rad_s) && isfinite(d.speed_kp_a_per_rad_s) && ...
            d.speed_kp_a_per_rad_s>0 && isscalar(d.max_target_rpm) && isfinite(d.max_target_rpm) && ...
            d.max_target_rpm>0 && d.max_target_rpm*2*pi/60<limits(3), ...
            'Verify speed gain and an RPM reference limit below the overspeed trip.');
        assert(abs(opts.SpeedRPM)<=d.max_target_rpm,'Initial RPM exceeds the verified reference limit.');
        speedSettings = [d.speed_kp_a_per_rad_s d.max_target_rpm];
    end
end
policy = [];
if strlength(opts.Checkpoint)>0
    data = load(opts.Checkpoint,'agent');
    policy = furuta_pi_greedy_policy(data.agent);
end
assert(isfolder(opts.Folder),'Output folder does not exist.');
file = fullfile(opts.Folder,mdl+".slx");
if bdIsLoaded(mdl)
    assert(strcmp(get_param(mdl,'Dirty'),'off'),'Save or close the open model first.');
    close_system(mdl,0);
end
load_system('raspberrypiCommlib');
new_system(mdl);
guard = onCleanup(@() close_system(mdl,0));
% Pi 5 runs 64-bit Raspberry Pi OS. Switching HardwareBoard later resets CAN.BusSpeed0 to 500,
% so the board is fixed here, before the bus speed is written.
set_param(mdl,'HardwareBoard','Raspberry Pi (64bit)','Solver','FixedStepDiscrete', ...
    'FixedStep','0.005','StopTime','inf');
% The generated Pi app re-runs "ip link set can0 up type can bitrate <BusSpeed0>" at start,
% so every mode must carry the profile bitrate (default target value is 500 kbps).
cfg = getActiveConfigSet(mdl);
codertarget.data.setParameterValue(cfg,'CAN.BusSpeed0',num2str(profile.can.bitrate/1000));
codertarget.data.setParameterValue(cfg,'CAN.CANBusSpeed',num2str(profile.can.bitrate/1000));
assert(str2double(string(codertarget.data.getParameterValue(cfg,'CAN.BusSpeed0')))*1000==profile.can.bitrate, ...
    'CAN bus speed does not match the hardware profile.');
mw = get_param(mdl,'ModelWorkspace');
sensor = profile.pendulum_sensor;
armHome = profile.arm_home_deg;
if opts.AutoArmHome && ~opts.Verification
    armHome = NaN;   % furuta_pi_decode latches the first valid angle as home
end
assignin(mw,'calibration',[armHome profile.arm_sign sensor.upright_count sensor.sign]);
assignin(mw,'drive',drive);
assignin(mw,'limits',limits);
if opts.ManualCurrent
    assignin(mw,'manualCurrentA',opts.CurrentA);
end
if opts.SpeedControl
    assignin(mw,'motorSpeedRPM',opts.SpeedRPM);
    assignin(mw,'speedSettings',speedSettings);
end

sys = mdl;
if opts.Verification
    buildVerification();
    save_system(mdl,char(file));
    return
end
add('simulink/Sources/Digital Clock','Time',[25 475 85 505],'SampleTime','.005');
chart('CAN slots',[130 460 235 515],["function [query,act] = slots(t)"; ...
    "act = mod(round(t/.005),2)==1;";"query = ~act;";"end"]);
wire('Time/1','CAN slots/1');
tx('Angle request 0x92',[410 450 575 510],false);
wire('CAN slots/1','Angle request 0x92/Enable');

can = profile.can;
add('raspberrypiCommlib/CAN Receive','RMD reply',[25 30 150 115], ...
    'DeviceID',can.interface,'MessageId',num2str(can.angle_reply_id), ...
    'SampleTime','.005','OutputError','on','OutputRemote','on');
i2c('AS5600 magnet status',11,1,[25 140 150 185]);
i2c('AS5600 angle',14,2,[25 205 150 250]);
constant('Sensor calibration','calibration',[25 285 150 315]);
sampleFn = "furuta_pi_sample";
if opts.MissTolerance>0
    sampleFn = "furuta_pi_sample_tol";   % sorts replies by opcode (survives a one-slot reply lag), keeps rate filter over short gaps
end
chart('Sensor decoder',[285 30 445 320],["function [obs,valid,ack] = decode(frame,status,err,remote,magnet,mstat,angle,astat,cal,act)"; ...
    "[obs,valid,ack] = "+sampleFn+"(frame,status,err,remote,magnet,mstat,angle,astat,cal,act);";"end"]);
ackSource = 'Sensor decoder/3';
if opts.NativeSpeed
    chart('A2 feedback',[320 545 470 680],[
        "function [ack,iq] = feedback(frame,status,err,remote)"
        "ack=frame(1)==162 && status==1 && err==0 && remote==0;"
        "iq=NaN;"
        "if ack"
        "    counts=double(frame(3))+256*double(frame(4));"
        "    if counts>=32768, counts=counts-65536; end"
        "    iq=counts/100;"
        "end"
        "end"]);
    for k=1:4, wire(sprintf('RMD reply/%d',k),sprintf('A2 feedback/%d',k)); end
    add('simulink/Discrete/Unit Delay','Previous A2 ack',[500 555 555 585], ...
        'SampleTime','.005','InitialCondition','false');
    add('simulink/Discrete/Unit Delay','Previous A2 current',[500 620 555 650], ...
        'SampleTime','.005','InitialCondition','NaN');
    wire('A2 feedback/1','Previous A2 ack/1');
    wire('A2 feedback/2','Previous A2 current/1');
    add('simulink/Sinks/Terminator','Unused A1 acknowledgement',[465 290 485 310]);
    wire(ackSource,'Unused A1 acknowledgement/1');
    ackSource = 'Previous A2 ack/1';
end
inputs = {'RMD reply/1','RMD reply/2','RMD reply/3','RMD reply/4', ...
    'AS5600 magnet status/1','AS5600 magnet status/2','AS5600 angle/1','AS5600 angle/2', ...
    'Sensor calibration/1','CAN slots/2'};
for k=1:numel(inputs)
    wire(inputs{k},sprintf('Sensor decoder/%d',k));
end
constant('Drive calibration','drive',[520 245 640 275]);
if opts.ManualCurrent
    constant('Current reference A','manualCurrentA',[480 25 550 55]);
    chart('Current reference to action',[620 35 710 97],[
        "function a = normalize(iq,d)"
        "a = 0;"
        "if d(2)>0, a = d(1)*iq/d(2); end"
        "end"]);
    wire('Current reference A/1','Current reference to action/1');
    wire('Drive calibration/1','Current reference to action/2');
    source = 'Current reference to action/1';
elseif opts.SpeedControl
    constant('Speed reference RPM','motorSpeedRPM',[480 25 545 55]);
    constant('Speed settings','speedSettings',[480 90 545 120]);
    chart('Speed controller',[600 28 715 186],[
        "function [a,target] = control(rpm,obs,s,d)"
        "a = 0;"
        "target = max(-s(2),min(s(2),rpm));"
        "if ~isfinite(rpm), a = NaN; target = NaN; return, end"
        speedCommand()
        "end"]);
    wire('Speed reference RPM/1','Speed controller/1');
    wire('Sensor decoder/1','Speed controller/2');
    wire('Speed settings/1','Speed controller/3');
    wire('Drive calibration/1','Speed controller/4');
    source = 'Speed controller/1';
elseif strlength(opts.ControllerFunction)>0
    % Stateful controller: update only on actuation ticks with a valid fresh sample, hold otherwise.
    % An invalid sample resets the controller (observer, capture latch, integrator).
    assert(exist(char(opts.ControllerFunction),'file')==2,'Controller function not found on the path.');
    chart('Classical controller',[500 36 605 99],[
        "function [a,balancing] = control(obs,valid,act)"
        "persistent last bal miss"
        "if isempty(last), last = 0; bal = false; miss = 0; end"
        "x = [obs(3); atan2(obs(2),obs(1)); obs(4); obs(5)];"
        "if ~valid"
        "    if act, miss = miss + 1; end"
        "    if miss > "+string(opts.MissTolerance)+" || "+string(opts.MissTolerance)+" == 0"
        "        [~,~] = "+opts.ControllerFunction+"(x,false); last = 0; bal = false;"
        "    end"
        "elseif act"
        "    miss = 0;"
        "    [last,bal] = "+opts.ControllerFunction+"(x,true);"
        "end"
        "a = last; balancing = bal;"
        "end"]);
    wire('Sensor decoder/1','Classical controller/1');
    wire('Sensor decoder/2','Classical controller/2');
    wire('CAN slots/2','Classical controller/3');
    add('simulink/Sinks/Terminator','Balance flag',[640 80 660 100]);
    wire('Classical controller/2','Balance flag/1');
    source = 'Classical controller/1';
elseif strlength(opts.PolicyFunction)>0
    % The checkpoint agent must match the plain function (checked here on sample observations).
    fn = str2func(char(opts.PolicyFunction));
    for x = [-1 -.98 .2 1 .9; 0 .2 -.98 0 .44; 0 .3 7 -2.5 1; 0 1 -.6 3 -8; 0 .5 -.9 -6 12]
        y = x; y(3) = atan2(sin(x(3)),cos(x(3)));
        reference = getAction(policy,{y});
        assert(abs(double(reference{1})-fn(x))<1e-5,'Policy function differs from the checkpoint greedy policy.');
    end
    chart('PPO swing-up policy',[500 36 605 79],["function a = infer(obs)"; ...
        "a = "+opts.PolicyFunction+"(obs);";"end"]);
    wire('Sensor decoder/1','PPO swing-up policy/1');
    source = 'PPO swing-up policy/1';
elseif opts.CurriculumPolicy
    script = furuta_curriculum_actor_script(data.agent,policy);
    chart('PPO curriculum policy',[500 36 605 79],script);
    wire('Sensor decoder/1','PPO curriculum policy/1');
    source = 'PPO curriculum policy/1';
elseif ~isempty(policy)
    % Infer on the base tick so the actuation slot uses the just-decoded observation.
    policy.SampleTime = .005;
    [~,suffix] = fileparts(tempname);
    old = cd(opts.Folder);
    restoreFolder = onCleanup(@() cd(old));
    generated = generatePolicyBlock(policy,MATFileName="furutaPolicy_"+string(suffix));
    closeGenerated = onCleanup(@() close_system(generated,0));
    set_param(mdl,'SimTargetLang','C++','TargetLang','C++');
    add([char(generated) '/Policy'],'PPO or SAC policy',[500 36 605 79]);
    clear closeGenerated restoreFolder
    wire('Sensor decoder/1','PPO or SAC policy/1');
    source = 'PPO or SAC policy/1';
else
    constant('PPO or SAC policy','0',[500 36 605 79]);
    source = 'PPO or SAC policy/1';
end
requested = source;
constant('Drive envelope','limits',[520 300 640 330]);
if opts.NativeSpeed
    chart('Drive interlocks',[730 35 905 365],[ ...
        "function [packet,send,applied] = command(rpm,obs,valid,act,ack,d,lim,t,cal,s,iq)"; ...
        "persistent needsAck"; ...
        "if isempty(needsAck), needsAck = false; end"; ...
        "packet = zeros(1,8,'uint8'); send = false; applied = 0;"; ...
        "if ~act || d(4)==0, return, end"; ...
        "ok = valid && (~needsAck || (ack && isfinite(iq) && abs(iq)<=d(3)));"; ...
        "armed = valid || needsAck || t>.2;"; ...
        "[packet,send,applied] = furuta_pi_speed_frame(rpm,obs,ok,armed,cal(2),s(2),s(1),lim,t,d(4));"; ...
        "needsAck = packet(1)==162;";"end"]);
else
if opts.MissTolerance>0
    frameCall = "[packet,send,applied] = furuta_pi_frame_tol(a,obs,valid && (~needsAck || ack),engaged,d(1),d(2),d(3),lim,t,d(4),"+string(opts.MissTolerance)+");";
else
    frameCall = "[packet,send,applied] = furuta_pi_frame(a,obs,valid && (~needsAck || ack),engaged,d(1),d(2),d(3),lim,t,d(4));";
end
chart('Drive interlocks',[730 35 905 365],[ ...
    "function [packet,send,applied] = command(a,obs,valid,act,ack,d,lim,t)"; ...
    "persistent needsAck count"; ...
    "if isempty(needsAck), needsAck = false; count = 0; end"; ...
    "packet = zeros(1,8,'uint8'); send = false; applied = 0;"; ...
    "if ~act || d(4)==0, return, end"; ...
    "if valid, count = count+1; end"; ...
    "engaged = count>0 || t>.2;"; ...
    frameCall; ...
    "needsAck = packet(1)==161;";"end"]);
end
inputs = {source,'Sensor decoder/1','Sensor decoder/2','CAN slots/2', ...
    ackSource,'Drive calibration/1','Drive envelope/1','Time/1'};
if opts.NativeSpeed
    inputs = [inputs,{'Sensor calibration/1','Speed settings/1','Previous A2 current/1'}];
end
for k=1:numel(inputs)
    wire(inputs{k},sprintf('Drive interlocks/%d',k));
end
tx('Motor CAN transmit',[1010 105 1175 175],true);
wire('Drive interlocks/1','Motor CAN transmit/1');
wire('Drive interlocks/2','Motor CAN transmit/Enable');
source = 'Drive interlocks/3';
statusSource = 'Drive interlocks/1';
if opts.SpeedControl
    chart('Speed feedback',[1250 430 1410 590],[
        "function row = feedback(requested,target,obs,valid,phase)"
        "persistent measured"
        "if isempty(measured), measured = NaN; end"
        "if phase"
        "    measured = NaN;"
        "    if valid, measured = obs(4)*60/(2*pi); end"
        "end"
        "row = [requested;target;measured];"
        "end"]);
    inputs = {'Speed reference RPM/1','Speed controller/2','Sensor decoder/1', ...
        'Sensor decoder/2','CAN slots/2'};
    for k=1:numel(inputs)
        wire(inputs{k},sprintf('Speed feedback/%d',k));
    end
    add('simulink/Sinks/Scope','Motor speed Scope',[1495 470 1540 510]);
    line = wire('Speed feedback/1','Motor speed Scope/1');
    set_param(line,'Name','furutaMotorSpeedRPM');
    ports = get_param([mdl '/Speed feedback'],'PortHandles');
    set_param(ports.Outport,'DataLogging','on');
end
if opts.NativeSpeed
    add('simulink/Sinks/Scope','A2 reported current Scope',[1495 575 1540 615]);
    h = wire('A2 feedback/2','A2 reported current Scope/1');
    set_param(h,'Name','furutaA2ReportedCurrentA');
    ports = get_param([mdl '/A2 feedback'],'PortHandles');
    set_param(ports.Outport(2),'DataLogging','on');
end
if opts.ManualCurrent
    chart('Motor current feedback',[1250 415 1420 600],[
        "function [row,opcode] = feedback(target,packet,frame,ack,phase)"
        "persistent sent code iq"
        "if isempty(code), sent=NaN; code=uint8(0); iq=NaN; end"
        "if phase"
        "    code=packet(1); sent=NaN;"
        "    if code==161"
        "        bits=bitor(uint16(packet(5)),bitshift(uint16(packet(6)),8));"
        "        sent=double(typecast(bits,'int16'))/100;"
        "    end"
        "    if code~=161, iq=NaN; end"
        "else"
        "    iq=NaN;"
        "    if code==161 && ack"
        "        bits=bitor(uint16(frame(3)),bitshift(uint16(frame(4)),8));"
        "        iq=double(typecast(bits,'int16'))/100;"
        "    end"
        "end"
        "row=[target;sent;iq]; opcode=double(code);"
        "end"]);
    wire('Current reference A/1','Motor current feedback/1');
    wire('Drive interlocks/1','Motor current feedback/2');
    wire('RMD reply/1','Motor current feedback/3');
    wire('Sensor decoder/3','Motor current feedback/4');
    wire('CAN slots/2','Motor current feedback/5');
    add('simulink/Sinks/Scope','Motor current Scope',[1495 470 1540 510]);
    line = wire('Motor current feedback/1','Motor current Scope/1');
    set_param(line,'Name','furutaMotorCurrent');
    ports = get_param([mdl '/Motor current feedback'],'PortHandles');
    set_param(ports.Outport(1),'DataLogging','on');
    add('simulink/Sinks/Display','Motor opcode',[1495 535 1570 570]);
    line = wire('Motor current feedback/2','Motor opcode/1');
    set_param(line,'Name','furutaMotorOpcode');
    set_param(ports.Outport(2),'DataLogging','on');
end
chart('Telemetry',[1250 45 1420 330],[...
    "function row = logrow(t,obs,valid,act,ack,a,packet,requested)"; ...
    "row = [t; double(act); double(valid); obs; a; double(packet(1)); double(ack); double(requested)];";"end"]);
inputs = {'Time/1','Sensor decoder/1','Sensor decoder/2','CAN slots/2', ...
    ackSource,source,statusSource,requested};
for k=1:numel(inputs)
    wire(inputs{k},sprintf('Telemetry/%d',k));
end
add('simulink/Sinks/Out1','Pi telemetry',[1495 160 1540 185]);
line = wire('Telemetry/1','Pi telemetry/1');
name = 'furutaPiTelemetry';
if opts.NativeSpeed, name = 'furutaA2Telemetry'; end
set_param(line,'Name',name);
ports = get_param([mdl '/Telemetry'],'PortHandles');
set_param(ports.Outport,'DataLogging','on');
% Sensor-path health (added 2026-11-20 after a run lost valid samples during fast arm motion):
% CAN status/error/remote of the RMD reply, first reply byte, AS5600 magnet byte and both I2C status codes.
chart('Health log',[1250 360 1420 470],[ ...
    "function row = health(frame,status,err,remote,magnet,mstat,astat)"; ...
    "row = [double(status); double(err); double(remote); double(frame(1)); double(magnet(1)); double(mstat); double(astat)];";"end"]);
hin = {'RMD reply/1','RMD reply/2','RMD reply/3','RMD reply/4','AS5600 magnet status/1','AS5600 magnet status/2','AS5600 angle/2'};
for k=1:numel(hin)
    wire(hin{k},sprintf('Health log/%d',k));
end
hp = get_param([mdl '/Health log'],'PortHandles');
set_param(hp.Outport,'DataLogging','on','DataLoggingNameMode','Custom','DataLoggingName','furutaPiHealth');
if opts.TimingLog
    chart('Timing log',[1250 500 1420 560],["function row = timing(t)";"row = furuta_pi_timing(t);";"end"]);
    wire('Time/1','Timing log/1');
    tp = get_param([mdl '/Timing log'],'PortHandles');
    set_param(tp.Outport,'DataLogging','on','DataLoggingNameMode','Custom','DataLoggingName','furutaPiTiming');
end
set_param(mdl,'SignalLogging','on');
if opts.SpeedControl
    furuta_pi_enable_speed_tuning(mdl);
end
if opts.ManualCurrent
    furuta_pi_enable_current_tuning(mdl);
end
save_system(mdl,char(file));

    function statement = speedCommand()
        if opts.NativeSpeed
            statement = "a = target;";
        else
            statement = "if d(2)>0, a = s(1)*(target*(2*pi/60)-obs(4))/d(2); end";
        end
    end

    function buildVerification()
        add('simulink/Sources/Digital Clock','Time',[25 30 80 58],'SampleTime','.005');
        chart('Read-only CAN schedule',[135 22 275 80],[ ...
            "function [packet,query,expected] = schedule(t)"; ...
            "tick = round(t/.005);"; ...
            "codes = uint8([146 154 156]);"; ...
            "expected = codes(mod(floor(tick/2),3)+1);"; ...
            "query = mod(tick,2)==0;"; ...
            "packet = [expected zeros(1,7,'uint8')];";"end"]);
        wire('Time/1','Read-only CAN schedule/1');
        tx('RMD read requests',[390 25 545 85],true);
        wire('Read-only CAN schedule/1','RMD read requests/1');
        wire('Read-only CAN schedule/2','RMD read requests/Enable');
        add('raspberrypiCommlib/CAN Receive','RMD replies',[25 135 160 218], ...
            'DeviceID',profile.can.interface,'MessageId',num2str(profile.can.angle_reply_id), ...
            'SampleTime','.005','OutputError','on','OutputRemote','on');
        i2c('AS5600 magnet status',11,1,[25 250 160 298]);
        i2c('AS5600 angle',14,2,[25 330 160 378]);
        constant('Sensor calibration','calibration',[25 410 160 440]);
        chart('Bench diagnostics',[380 152 575 455],[ ...
            "function [electrical,angles,health] = diagnostics(frame,rx,err,remote,mag,ms,angle,as,cal,query,expected)"; ...
            "[electrical,angles,health] = furuta_pi_verify_sample(frame,rx,err,remote,mag,ms,angle,as,cal,query,expected);";"end"]);
        inputs = {'RMD replies/1','RMD replies/2','RMD replies/3','RMD replies/4', ...
            'AS5600 magnet status/1','AS5600 magnet status/2','AS5600 angle/1','AS5600 angle/2', ...
            'Sensor calibration/1','Read-only CAN schedule/2','Read-only CAN schedule/3'};
        for k=1:numel(inputs)
            wire(inputs{k},sprintf('Bench diagnostics/%d',k));
        end
        ports = get_param([mdl '/Bench diagnostics'],'PortHandles');
        names = {'Electrical','Angles','Health'};
        for k=1:numel(names)
            name = [names{k} ' Scope'];
            y = 180+(k-1)*90;
            add('simulink/Sinks/Scope',name,[730 y 785 y+40]);
            h = wire(sprintf('Bench diagnostics/%d',k),[name '/1']);
            set_param(h,'Name',['furutaVerify' names{k}]);
            set_param(ports.Outport(k),'DataLogging','on');
        end
        set_param(mdl,'SignalLogging','on');
    end

    function add(lib,name,pos,varargin)
        add_block(lib,[sys '/' name],'Position',pos,varargin{:});
    end
    function handle = wire(from,to)
        if endsWith(to,'/Enable')
            n = extractBefore(to,'/Enable');
            parts = split(from,'/');
            src = get_param([sys '/' char(parts(1))],'PortHandles');
            dst = get_param([sys '/' char(n)],'PortHandles');
            handle = add_line(sys,src.Outport(str2double(parts(2))),dst.Enable,'autorouting','on');
        else
            handle = add_line(sys,from,to,'autorouting','on');
        end
    end
    function constant(name,value,pos)
        add('simulink/Sources/Constant',name,pos,'Value',value,'SampleTime','.005');
    end
    function chart(name,pos,script)
        add('simulink/User-Defined Functions/MATLAB Function',name,pos);
        r = sfroot;
        c = r.find('-isa','Stateflow.EMChart','Path',[sys '/' name]);
        c.Script = char(join(script,newline));
    end
    function i2c(name,reg,count,pos)
        add('raspberrypiCommlib/I2C Controller Read',name,pos, ...
            'BoardProperty',char(opts.I2CBoard),'I2CModule',num2str(sensor.i2c_bus), ...
            'SlaveAddress',num2str(sensor.i2c_address), ...
            'RegisterAddress',num2str(reg),'DataLength',num2str(count), ...
            'SampleTime','.005','OutputStatus','on','RepeatedStart','on');
    end
    function tx(name,pos,externalPayload)
        add('simulink/Ports & Subsystems/Enabled Subsystem',name,pos);
        sys = [mdl '/' name];
        Simulink.SubSystem.deleteContents(sys);
        add('simulink/Ports & Subsystems/Enable','Enable',[150 15 180 45]);
        if externalPayload
            add('simulink/Sources/In1','Payload',[35 90 65 110]);
        else
            constant('Payload','uint8([146 0 0 0 0 0 0 0])',[20 80 100 110]);
        end
        add('raspberrypiCommlib/CAN Transmit','CAN Transmit',[200 75 320 115], ...
            'DeviceID',profile.can.interface,'MessageId',num2str(profile.can.request_id));
        wire('Payload/1','CAN Transmit/1');
        furuta_pi_format_can_tx([sys '/CAN Transmit']);
        sys = mdl;
    end
end

