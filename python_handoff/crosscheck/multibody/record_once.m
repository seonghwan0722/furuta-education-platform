% One MATLAB session: load the rev11 Multibody model (view already set in the model), replay the sac24 ck_0100
% trajectory, record with smwritevideo, wait until the MP4 is fully written, then quit MATLAB.
here = 'C:/Capstone1/mujoco_crosscheck/multibody'; cd(here);
S = load(fullfile(here,'trajectory.mat'));
assignin('base','armQ',timeseries(S.th,S.t)); assignin('base','pendQ',timeseries(S.alpha,S.t));
mdl = 'furuta_rev11_multibody_show'; load_system(fullfile(here,[mdl '.slx']));
set_param(mdl,'SimMechanicsOpenEditorOnUpdate','on');
sim(mdl);
f = fullfile(here,'sac24_ck0100_multibody_record.mp4'); if isfile(f), delete(f); end
smwritevideo(mdl, f(1:end-4), 'PlaybackSpeedRatio', 1, 'FrameRate', 30, 'VideoFormat', 'mpeg-4');
last = -1; stable = 0;
for w = 1:300                       % up to 10 min; the writer finishes in the background
    pause(2); d = dir(f);
    if ~isempty(d) && d.bytes > 0 && d.bytes == last, stable = stable + 1; else, stable = 0; end
    if ~isempty(d), last = d.bytes; end
    if stable >= 3, break; end
end
fid = fopen(fullfile(here,'record_once.done'),'w'); fprintf(fid,'%d bytes\n',last); fclose(fid);
close_system(mdl,0); exit
