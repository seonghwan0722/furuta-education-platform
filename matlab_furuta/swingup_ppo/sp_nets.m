function [actor,critic,logStd] = sp_nets(hA,hC,std0)
actor = dlnetwork([featureInputLayer(5,Name="obs") fullyConnectedLayer(hA,Name="fc1") tanhLayer(Name="t1") ...
    fullyConnectedLayer(hA,Name="fc2") tanhLayer(Name="t2") fullyConnectedLayer(1,Name="fc3") tanhLayer(Name="mean")]);
critic = dlnetwork([featureInputLayer(5,Name="obs") fullyConnectedLayer(hC,Name="fc1") tanhLayer ...
    fullyConnectedLayer(hC,Name="fc2") tanhLayer fullyConnectedLayer(1,Name="v")]);
logStd = dlarray(log(std0));
end
