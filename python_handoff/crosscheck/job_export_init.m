% Export the MATLAB benchmark starting points and configs (read-only) for the PyTorch stability runs.
base='C:/Capstone1/matlab_furuta/results/ppo_swingup_20261119/'; out='C:/Capstone1/mujoco_crosscheck/stability/';
L2S=@(net) cell2struct(cellfun(@(v) double(extractdata(v)),net.Learnables.Value,'UniformOutput',false), ...
    strcat(string(net.Learnables.Layer),'_',string(net.Learnables.Parameter)));
S=load([base 'sac19_rev11_regen/ck_0150.mat']); C=load([base 'sac24_rev11_armrate2/config.mat']);
E=struct('actor',L2S(S.sacActor),'bank',S.bank,'cfg',C.cfg);
fid=fopen([out 'init_sac.json'],'w'); fprintf(fid,'%s',jsonencode(E,'ConvertInfAndNaN',true)); fclose(fid);
P=load([base 'run10_rev11_bias/ck_0250.mat']); C=load([base 'run12_rev11_hold_lo/config.mat']);
E=struct('actor',L2S(P.actor),'critic',L2S(P.critic),'logStd',double(extractdata(P.logStd)),'bank',P.bank,'cfg',C.cfg);
fid=fopen([out 'init_ppo.json'],'w'); fprintf(fid,'%s',jsonencode(E,'ConvertInfAndNaN',true)); fclose(fid);
disp('EXPORT_OK')
