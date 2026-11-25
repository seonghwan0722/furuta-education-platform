% Replay the saved sac24 ck_0100 trajectory in the rev11 Multibody model (Mechanics Explorer) and save an MP4.
here = 'C:/Capstone1/mujoco_crosscheck/multibody'; cd(here);
S = load(fullfile(here,'trajectory.mat'));
assignin('base','armQ',timeseries(S.th,S.t)); assignin('base','pendQ',timeseries(S.alpha,S.t));
mdl = 'furuta_rev11_multibody_show';
open_system(fullfile(here,[mdl '.slx']));
set_param(mdl,'SimMechanicsOpenEditorOnUpdate','on');
sim(mdl);
fprintf('SIM_DONE %s reach %.2f s\n', S.ckName, S.M.ReachTime);
vid = fullfile(here,'sac24_ck0100_multibody');
try
    smwritevideo(mdl, vid, 'PlaybackSpeedRatio', 1, 'FrameRate', 30, 'VideoFormat', 'mpeg-4');
    fprintf('VIDEO_DONE %s.mp4\n', vid);
catch e
    fprintf('VIDEO_FAILED %s\n', e.message);
end
