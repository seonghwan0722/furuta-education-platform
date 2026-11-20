function checkpoint = train_furuta_ppo_curriculum(opts)
% Offline curriculum with deterministic checks before each increase in difficulty.
arguments
    opts.HardwareCandidate (1,1) logical = false
    opts.ArmInertia (1,1) double = NaN
    opts.CoulombTorque (1,1) double = NaN
    opts.Episodes (1,1) double {mustBePositive,mustBeInteger} = 24
    opts.CandidateMaxStartDeg (1,1) double {mustBeMember(opts.CandidateMaxStartDeg,[5 13 20])} = 20
    opts.InitialCheckpoint (1,1) string = ""
    opts.EpisodeSeconds (1,1) double {mustBePositive,mustBeFinite} = 5
    opts.ArmRateLimit (1,1) double {mustBePositive,mustBeFinite}
    opts.ActionDelaySeconds (1,1) double {mustBeNonnegative,mustBeFinite} = .01
    opts.ArmAngleLimit (1,1) double {mustBePositive}
    opts.PendRateLimit (1,1) double {mustBePositive,mustBeFinite}
end
checkpoint = "";
if opts.HardwareCandidate
    validateattributes(opts.ArmInertia,{'double'},{'positive','finite'});
    validateattributes(opts.CoulombTorque,{'double'},{'nonnegative','finite'});
end
build_furuta_rl;
model = 'furuta_rl_training';
cleanup = onCleanup(@() close_system(model,0));
mw = get_param(model,'ModelWorkspace');
actuation = furuta_configure_training_delay(model,opts.ActionDelaySeconds);
p = furuta_params;
motor = getVariable(mw,'rmd');
profile = jsondecode(fileread(fullfile(fileparts(mfilename('fullpath')), ...
    '..','deployment','pi','rmd_speed_drive_candidate.json')));
if isfield(opts,'ArmRateLimit'), profile.limits(3)=opts.ArmRateLimit; end
if isfield(opts,'PendRateLimit'), profile.limits(4)=opts.PendRateLimit; end
armLimit = profile.limits(1);
if isfield(opts,'ArmAngleLimit'), armLimit=opts.ArmAngleLimit; end
ampsPerAction = p.tau_max/motor.Kt;
if opts.HardwareCandidate
    ampsPerAction = profile.amps_per_action;
    assert(ampsPerAction==profile.max_current_a && ...
        abs(round(ampsPerAction/motor.currentLSB)*motor.currentLSB-ampsPerAction)<1e-12, ...
        'The candidate requires a full-scale current equal to the cap and on the A1 current grid.');
    % alpha is the effective arm inertia at the upright position.
    p.alpha = opts.ArmInertia;
    p.coulomb = opts.CoulombTorque;
    p.tau_max = ampsPerAction*motor.Kt;
    assignin(mw,'maxTorque',p.tau_max);
    assignin(mw,'plantCoefficients',furuta_block_coefficients(p));
end
assert(ampsPerAction<=profile.max_current_a,'Nominal mapping exceeds the tested current ceiling.');
fprintf('NOMINAL MAP %.6f Nm/action, %.6f A/action, %.0f available A1 counts\n', ...
    p.tau_max,ampsPerAction,floor(ampsPerAction/motor.currentLSB));

root = sfroot;
chart = root.find('-isa','Stateflow.EMChart','Path', ...
    [model '/03 Controllers/RL observation reward termination']);
old = char(chart.Script);
assert(contains(old,'abs(x(1))>2*pi'),'Unexpected training termination expression.');
limitTest = sprintf('abs(x(1))>%.17g',armLimit);
if opts.HardwareCandidate
    limitTest = sprintf('(%s || abs(x(3))>=%.17g || abs(x(4))>=%.17g)', ...
        limitTest,profile.limits(3),profile.limits(4));
end
chart.Script = strrep(old,'abs(x(1))>2*pi',limitTest);

folder = fullfile(results_dir,'ppo_curriculum');
if opts.HardwareCandidate
    folder = tempname(results_dir);
    [parent,name] = fileparts(folder);
    folder = fullfile(parent,['ppo_rmd_candidate_' name]);
end
if ~isfolder(folder), mkdir(folder); end
rng(314,'twister');
agent = furuta_make_agent("PPO",p.Ts);
if opts.HardwareCandidate
    linearParams = p;
    linearParams.coulomb = 0;
    [~,~,A,B] = furuta_linearize(linearParams,false);
    K = riccati_gain(A,B,diag([10 10 1 1]),1,false);
else
    K = getVariable(mw,'lqrGain');
end
agent = setActor(agent,warmStart(K,agent));
if strlength(opts.InitialCheckpoint)>0
    initial = load(opts.InitialCheckpoint,'agent');
    furuta_pi_greedy_policy(initial.agent);
    agent = initial.agent;
end
env = rlSimulinkEnv(model,[model '/03 Controllers/RL Agent'], ...
    getObservationInfo(agent),getActionInfo(agent),'UseFastRestart','on');
env.ResetFcn = @reset;
stages = [5 20 60 120 180];
if opts.HardwareCandidate
    stages = unique([5 opts.CandidateMaxStartDeg]);
    stages = stages(stages<=opts.CandidateMaxStartDeg);
end
best = "";
for stage=stages
    fprintf('STAGE %d START\n',stage);
    options=rlTrainingOptions(MaxEpisodes=opts.Episodes, ...
        MaxStepsPerEpisode=round(opts.EpisodeSeconds/p.Ts), ...
        StopTrainingCriteria="EpisodeCount",StopTrainingValue=opts.Episodes, ...
        Plots="none",Verbose=true,ScoreAveragingWindowLength=8);
    stats=train(agent,env,options);
    agent=setopt(agent,'UseExplorationPolicy',false);
    ideal=evaluate(agent,stage,true);
    filename=fullfile(folder,sprintf('ppo_%03ddeg.mat',stage));
    save(filename,'agent','stats','ideal','stage','ampsPerAction','armLimit','p','opts','profile','actuation');
    checkpoint = string(filename);
    fprintf('STAGE %d IDEAL %d/%d PASS\n',stage,nnz(ideal.Passed),height(ideal));
    if ~all(ideal.Passed)
        break
    end
    best = string(filename);
end
if opts.HardwareCandidate
    fprintf('PC ONLY candidate results: %s\n',folder);
    return
end
if strlength(best)==0
    disp('No trained checkpoint passed the first stage.');
    return
end
data=load(best,'agent','stage');
rmdCheck=evaluate(data.agent,data.stage,true);
save(best,'rmdCheck','-append');
fprintf('RMD NOMINAL-MAPPING %d/%d PASS\n',nnz(rmdCheck.Passed),height(rmdCheck));
addpath(folder);
deploy=build_furuta_pi_hardware(Checkpoint=best,Folder=folder,CurriculumPolicy=true);
m='furuta_pi_hardware_policy';
load_system(deploy);
mwPi=get_param(m,'ModelWorkspace');
assert(all(getVariable(mwPi,'drive')==0),'Policy check model must stay locked.');
set_param(m,'GenCodeOnly','on','RTWVerbose','off');
slbuild(m);
close_system(m,0);
fprintf('LOCKED PI POLICY CODEGEN PASS %s\n',deploy);

    function in=reset(in)
        x0=[0;deg2rad(stage)*(2*rand-1);0;0];
        in=in.setVariable('initialState',x0,Workspace=model);
        in=in.setVariable('controllerMode',5,Workspace=model);
        in=in.setVariable('usePolicyCallback',0,Workspace=model);
        in=in.setVariable('useRmd',1,Workspace=model);
        in=in.setVariable('rmdCommandDelaySamples',actuation.commandDelaySamples,Workspace=model);
        in=in.setVariable('rlRewardLevel',2,Workspace=model);
    end

    function report=evaluate(policy,range,useRmd)
        % Fixed holdout starts are separate from the random training resets.
        angles=range*[-.95 -.53 .29 .81];
        if range==180, angles=[angles -180 180]; end
        values=zeros(numel(angles),4);
        for k=1:numel(angles)
            in=Simulink.SimulationInput(model);
            in=in.setVariable('furutaAgent',policy,Workspace=model);
            in=in.setVariable('initialState',[0;deg2rad(angles(k));0;0],Workspace=model);
            in=in.setVariable('controllerMode',5,Workspace=model);
            in=in.setVariable('usePolicyCallback',0,Workspace=model);
            in=in.setVariable('useRmd',double(useRmd),Workspace=model);
            in=in.setVariable('rmdCommandDelaySamples',actuation.commandDelaySamples,Workspace=model);
            in=in.setVariable('rlRewardLevel',2,Workspace=model);
            in=in.setModelParameter('StopTime','5','ReturnWorkspaceOutputs','on');
            out=sim(in);
            x=out.stateTrace;
            if size(x,2)~=4, x=reshape(x,4,[]).'; end
            err=abs(atan2(sin(x(:,2)),cos(x(:,2))));
            t=(0:numel(err)-1)'*p.Ts;
            last=t>=4-1e-9;
            held=any(last) && t(end)>=5-1e-9 && all(err(last)<.35);
            if opts.HardwareCandidate
                held=held && all(abs(x(:,3))<profile.limits(3)) && all(abs(x(:,4))<profile.limits(4));
            end
            values(k,:)=[angles(k),rad2deg(err(end)),max(abs(x(:,1))),held && all(isfinite(x),'all') && all(abs(x(:,1))<armLimit)];
        end
        report=array2table(values,'VariableNames',{'StartDeg','FinalErrorDeg','PeakArmRad','Passed'});
        report.Passed=logical(report.Passed);
        disp(report);
    end
end

function actor=warmStart(K,agent)
% Initialize the local mean from normalized LQR using sin(theta).
% A nonlinear residual can learn the wider-angle behavior.
net=dlnetwork;
net=addLayers(net,featureInputLayer(5,Normalization="none",Name="obs"));
gain=fullyConnectedLayer(1,Name="balance_prior");
gain.Weights=single([0 -K(2) -K(1) -K(3) -K(4)]);
gain.Bias=single(0);
net=addLayers(net,gain);
residual=fullyConnectedLayer(1,Name="residual",WeightsInitializer="zeros");
net=addLayers(net,[fullyConnectedLayer(32,Name="hidden"); tanhLayer(Name="features"); residual]);
net=addLayers(net,[additionLayer(2,Name="sum"); tanhLayer(Name="mean")]);
std=fullyConnectedLayer(1,Name="std_fc",WeightsInitializer="zeros");
std.Bias=single(log(expm1(.08)));
net=addLayers(net,[std; softplusLayer(Name="std")]);
net=connectLayers(net,"obs","balance_prior");
net=connectLayers(net,"obs","hidden");
net=connectLayers(net,"obs","std_fc");
net=connectLayers(net,"balance_prior","sum/in1");
net=connectLayers(net,"residual","sum/in2");
net=initialize(net);
actor=rlContinuousGaussianActor(net,getObservationInfo(agent),getActionInfo(agent), ...
    ObservationInputNames="obs",ActionMeanOutputNames="mean", ...
    ActionStandardDeviationOutputNames="std");
end
