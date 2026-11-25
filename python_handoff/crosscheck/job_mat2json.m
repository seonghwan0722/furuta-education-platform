d='C:/Capstone1/mujoco_crosscheck/matlab_export/'; f=dir([d '*.mat']);
for k=1:numel(f), S=load([d f(k).name]); fid=fopen([d strrep(f(k).name,'.mat','.json')],'w'); fprintf(fid,'%s',jsonencode(S,'ConvertInfAndNaN',true)); fclose(fid); end
