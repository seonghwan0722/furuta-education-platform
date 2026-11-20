function policyFunction = export_furuta_pi_policy(checkpoint,folder)
% Export a deterministic 100 Hz Furuta actor for the Pi deployment model.
data = load(checkpoint,'agent');
policy = furuta_pi_greedy_policy(data.agent);
folder = string(folder);
if ~isfolder(folder)
    mkdir(folder);
end
old = cd(folder);
restore = onCleanup(@() cd(old));
policyFunction = "furutaPiPolicy";
assert(~isfile(policyFunction+".m") && ~isfile('furutaPiPolicyData.mat'), ...
    'Use a fresh output folder for each exported policy.');
generatePolicyFunction(policy,FunctionName=policyFunction,MATFileName="furutaPiPolicyData");
fn = str2func(char(policyFunction));
for obs = [1 cos(.1) cos(-.1); 0 sin(.1) sin(-.1); 0 .1 -.1; 0 .2 -.2; 0 .3 -.3]
    expected = getAction(policy,{obs});
    actual = fn(obs);
    assert(isscalar(actual) && isfinite(actual) && abs(double(actual)-double(expected{1}))<1e-5, ...
        'Generated policy differs from the MATLAB greedy policy.');
end
end
