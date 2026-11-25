function actuation = furuta_configure_training_delay(model,delaySeconds)
% Apply the agreed command-to-actuator delay to the lightweight RMD path.
arguments
    model (1,1) string
    delaySeconds (1,1) double {mustBeNonnegative,mustBeFinite} = .01
end
w=get_param(model,'ModelWorkspace');
period=getVariable(w,'controlPeriod');
samples=round(delaySeconds/period);
assert(abs(samples*period-delaySeconds)<1e-10, ...
    'Command delay must be an integer multiple of controlPeriod.');
path=model+"/04 Actuator/RMD X6 P20 60 E/Command delay";
assert(getSimulinkBlockHandle(path)>0,'The lightweight RMD command delay block is missing.');
assert(strcmp(get_param(path,'DelayLength'),'rmdCommandDelaySamples'), ...
    'The RMD delay block uses an unexpected delay expression.');
assignin(w,'rmdCommandDelaySamples',samples);
assignin(w,'useRmd',1);
actuation=struct('commandDelaySeconds',delaySeconds,'commandDelaySamples',samples, ...
    'controlPeriodSeconds',period,'rmdEnabled',true, ...
    'delayBasis','User-selected command delay assumption applied to the lightweight RMD command path.');
fprintf('TRAINING_ACTUATION delay=%g s samples=%d controlPeriod=%g s RMD=on\n', ...
    delaySeconds,samples,period);
end
