function script = furuta_curriculum_actor_script(agent,policy)
% Generate the deterministic forward pass of the curriculum actor.
actor = getActor(agent);
net = getModel(actor);
names = sort(string({net.Layers.Name}));
expected = sort(["obs","balance_prior","hidden","features","residual","sum","mean","std_fc","std"]);
assert(isequal(names(:),expected(:)),'Checkpoint does not use the curriculum actor architecture.');
prior = weights("balance_prior","Weights");
priorBias = weights("balance_prior","Bias");
hidden = weights("hidden","Weights");
hiddenBias = weights("hidden","Bias");
res = weights("residual","Weights");
resBias = weights("residual","Bias");
for x = [1 .98 .98 -1 .1;0 .2 -.2 0 .99;0 .3 -.3 0 -.4;0 1 -.6 0 2;0 .5 -.9 0 -2]
    reference = getAction(policy,{x});
    value = tanh(prior*x+priorBias+res*tanh(hidden*x+hiddenBias)+resBias);
    assert(abs(double(reference{1})-value)<1e-5,'Curriculum actor export differs from the greedy policy.');
end
script = [
    "function a = infer(obs)"
    "h = tanh("+mat2str(hidden,17)+"*obs+"+mat2str(hiddenBias,17)+");"
    "a = tanh("+mat2str(prior,17)+"*obs+("+mat2str(priorBias,17)+")+"+ ...
        mat2str(res,17)+"*h+("+mat2str(resBias,17)+"));"
    "end"];

    function value = weights(layer,parameter)
        params = net.Learnables;
        row = params.Layer==layer & params.Parameter==parameter;
        assert(nnz(row)==1,'Missing actor parameter %s/%s.',layer,parameter);
        value = double(extractdata(params.Value{row}));
    end
end
