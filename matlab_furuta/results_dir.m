function path = results_dir
% 작업 폴더와 무관하게 프로젝트 안에 기록한다.
path = fullfile(fileparts(mfilename('fullpath')),'results');
if ~isfolder(path)
    mkdir(path);
end
end
