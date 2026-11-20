function update_furuta_fixed_shadow
% Add read-only policy inference to the existing telemetry branch.
folder = fileparts(mfilename('fullpath'));
model = 'furuta_block_model_fixed';
file = fullfile(folder,[model '.slx']);
load_system(file);
assert(strcmp(get_param(model,'Dirty'),'off'), ...
    'Save or discard the open fixed model changes before updating.');
sys = [model '/03 Pi - Motor Control and Telemetry'];
enable = [sys '/Policy shadow enable'];
infer = [sys '/PPO shadow telemetry'];
telemetry = [sys '/Telemetry'];
root = sfroot;
logger = root.find('-isa','Stateflow.EMChart','Path',telemetry);
assert(contains(logger.Script,'logrow(requested,'),'Unexpected telemetry input order.');
telem = get_param(telemetry,'PortHandles');
requested = telem.Inport(1);
if getSimulinkBlockHandle(enable)>0
    ports = get_param(infer,'PortHandles');
    assert(source(requested)==ports.Outport,'Unexpected connection to the shadow chart.');
    return
end
checkpoint = load(fullfile(folder,'results','ppo_curriculum','ppo_020deg.mat'),'agent');
policy = furuta_pi_greedy_policy(checkpoint.agent);
actor = furuta_curriculum_actor_script(checkpoint.agent,policy);
backup = fullfile(folder,'furuta_block_model_fixed.before_policy_shadow.slx.bak');
if ~isfile(backup), copyfile(file,backup); end

load_system('simulink');
try
    add_block('simulink/Sources/Constant',enable,'Value','0','Position',[500 418 602 444]);
    add_block('simulink/User-Defined Functions/MATLAB Function',infer, ...
        'Position',[1110 400 1230 500]);
    chart = root.find('-isa','Stateflow.EMChart','Path',infer);
    chart.Script = char(join([
        "function action = shadow(requested,obs,valid,enabled)"
        "action = requested;"
        "if enabled"
        "    action = NaN;"
        "    if valid && all(isfinite(obs))"
        "        action = infer(obs);"
        "    end"
        "end"
        "end"
        actor],newline));
    old = source(requested);
    ports = get_param(infer,'PortHandles');
    delete_line(sys,old,requested);
    add_line(sys,old,ports.Inport(1),'autorouting','on');
    add_line(sys,'Sensor decoder/1','PPO shadow telemetry/2','autorouting','on');
    add_line(sys,'Sensor decoder/2','PPO shadow telemetry/3','autorouting','on');
    add_line(sys,'Policy shadow enable/1','PPO shadow telemetry/4','autorouting','on');
    add_line(sys,ports.Outport,requested,'autorouting','on');
    save_system(model,file);
catch err
    close_system(model,0);
    rethrow(err)
end
end

function handle = source(port)
handle = get_param(get_param(port,'Line'),'SrcPortHandle');
end
