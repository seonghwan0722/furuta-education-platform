function agent = sp_export_agent(ck)
% Convert trainer networks to an rlPPOAgent (observation scaling folded into fc1).
c=sp_config; sc=sp_scale; L=ck.actor.Learnables;
get=@(net,layer,par) double(extractdata(net.Learnables.Value{strcmp(net.Learnables.Layer,layer)&strcmp(net.Learnables.Parameter,par)}));
W1=get(ck.actor,'fc1','Weights')./sc'; b1=get(ck.actor,'fc1','Bias');
W2=get(ck.actor,'fc2','Weights'); b2=get(ck.actor,'fc2','Bias');
W3=get(ck.actor,'fc3','Weights'); b3=get(ck.actor,'fc3','Bias');
sd=exp(double(extractdata(ck.logStd)));
net=dlnetwork;
net=addLayers(net,featureInputLayer(5,Normalization="none",Name="obs"));
net=addLayers(net,[fullyConnectedLayer(numel(b1),Name="fc1",Weights=single(W1),Bias=single(b1)) tanhLayer(Name="t1") ...
    fullyConnectedLayer(numel(b2),Name="fc2",Weights=single(W2),Bias=single(b2)) tanhLayer(Name="t2") ...
    fullyConnectedLayer(1,Name="fc3",Weights=single(W3),Bias=single(b3)) tanhLayer(Name="mean")]);
net=addLayers(net,[fullyConnectedLayer(1,Name="std_fc",Weights=zeros(1,5,'single'),Bias=single(log(expm1(sd)))) softplusLayer(Name="std")]);
net=connectLayers(net,"obs","fc1"); net=connectLayers(net,"obs","std_fc");
net=initialize(net);
oi=rlNumericSpec([5 1]); ai=rlNumericSpec([1 1],LowerLimit=-1,UpperLimit=1);
actor=rlContinuousGaussianActor(net,oi,ai,ObservationInputNames="obs",ActionMeanOutputNames="mean",ActionStandardDeviationOutputNames="std");
C1=get(ck.critic,'fc1','Weights')./sc'; cb1=get(ck.critic,'fc1','Bias');
C2=get(ck.critic,'fc2','Weights'); cb2=get(ck.critic,'fc2','Bias');
C3=get(ck.critic,'v','Weights'); cb3=get(ck.critic,'v','Bias');
cn=dlnetwork([featureInputLayer(5,Name="obs") fullyConnectedLayer(numel(cb1),Weights=single(C1),Bias=single(cb1)) tanhLayer ...
    fullyConnectedLayer(numel(cb2),Weights=single(C2),Bias=single(cb2)) tanhLayer fullyConnectedLayer(1,Weights=single(C3),Bias=single(cb3))]);
critic=rlValueFunction(cn,oi);
opt=rlPPOAgentOptions(SampleTime=c.Ts,DiscountFactor=0.995);
agent=rlPPOAgent(actor,critic,opt);
agent=setopt(agent,'UseExplorationPolicy',false);
end
