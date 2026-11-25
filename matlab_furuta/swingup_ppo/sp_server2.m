function sp_server2(qname)
if nargin<1, qname='queue'; end
% Simple job runner: executes queue/job_*.m files in order, writes queue/<name>.log
here=fileparts(mfilename('fullpath')); addpath(here); addpath(fileparts(here));
q=fullfile(here,qname);
fprintf('SERVER READY\n');
while true
    f=dir(fullfile(q,'job_*.m'));
    if isempty(f), pause(0.5); if isfile(fullfile(q,'STOP')), break; end, continue; end
    [~,i]=sort({f.name}); f=f(i(1));
    src=fullfile(q,f.name); [~,name]=fileparts(f.name);
    code=fileread(src); delete(src);
    logf=fullfile(q,[name '.log']);
    diary(logf); diary on;
    t0=tic;
    try
        evalin('base',code);
        fprintf('\nJOB_OK %.1f s\n',toc(t0));
    catch e
        fprintf('\nJOB_ERROR %s\n%s\n',e.message,getReport(e,'extended','hyperlinks','off'));
    end
    diary off;
    movefile(logf,fullfile(q,[name '.done.log']));
    bdclose('all');
end
end
