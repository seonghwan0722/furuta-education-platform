% Render the saved sac24 ck_0100 trajectory with the rev11 CAD meshes (same meshes and joint layout as the
% Multibody model) from a fixed 3/4 view, with an angle/time overlay, to MP4. Works in -batch (offscreen).
here = 'C:/Capstone1/mujoco_crosscheck/multibody';
S = load(fullfile(here,'trajectory.mat')); fps = 30;
mdir = 'C:/Capstone1/sim2real_rev11/sim2real_rev11/rev11_model/meshes/';
base = {'base_print',[.82 .83 .85];'base_logo_blue',[.1 .35 .8];'base_metal',[.74 .76 .79];'base_pcb_02420c',[.01 .26 .05]; ...
        'base_other_af0202',[.69 .01 .01];'base_dark',[.12 .12 .14];'base_motor',[.15 .15 .17];'base_brass',[.8 .6 .22]};
arm  = {'arm_print',[.82 .83 .85];'arm_metal',[.74 .76 .79];'arm_logo_blue',[.1 .35 .8];'arm_pcb_021184',[.01 .07 .52];'arm_cable',[.75 .1 .1]};
pend = {'pend_print',[.95 .55 .15];'pend_magnet',[.4 .1 .3];'pend_tip_screw_black',[.08 .08 .09]};
f = figure('Visible','off','Color','w','Position',[0 0 1280 960]); ax = axes(f,'Position',[0 0 1 1]); hold(ax,'on'); axis(ax,'equal','off');
tA = hgtransform(ax); tP0 = hgtransform(tA); tP = hgtransform(tP0);
set(tP0,'Matrix',makehgtform('translate',[0 0 0.018]));
draw(ax,base,mdir); draw(tA,arm,mdir); draw(tP,pend,mdir);
xlim(ax,[-0.20 0.20]); ylim(ax,[-0.20 0.20]); zlim(ax,[-0.20 0.20]);
view(ax,[-38 20]); camproj(ax,'perspective'); camva(ax,9);
lighting(ax,'gouraud'); camlight(ax,'headlight'); light(ax,'Position',[0.5 -0.5 1]); material(ax,'dull');
txt = annotation(f,'textbox',[0.02 0.88 0.6 0.1],'String','','FontSize',16,'EdgeColor','none','FontName','Consolas');
annotation(f,'textbox',[0.02 0.02 0.96 0.06],'String',sprintf('SAC %s  |  rev11 식별 플랜트, 지연 10 ms, 30 ms 필터, 1.5 A  |  매달린 정지 상태에서 시작', strrep(S.ckName,'_','\_')), ...
    'FontSize',12,'EdgeColor','none','Color',[.3 .3 .3]);
v = VideoWriter(fullfile(here,'sac24_ck0100_rev11_iso.mp4'),'MPEG-4'); v.FrameRate = fps; v.Quality = 95; open(v);
tq = 0:1/fps:S.t(end); th = interp1(S.t,S.th,tq); al = interp1(S.t,S.alpha,tq);
for k = 1:numel(tq)
    set(tA,'Matrix',makehgtform('zrotate',th(k)));
    set(tP,'Matrix',makehgtform('xrotate',al(k)));
    err = rad2deg(atan2(sin(al(k)-pi),cos(al(k)-pi)));
    set(txt,'String',sprintf('t = %5.2f s   진자 오차 %+6.1f°   암 %+7.1f°', tq(k), err, rad2deg(th(k))));
    writeVideo(v,getframe(f));
end
close(v); fprintf('RENDER_DONE %d frames\n', numel(tq));

function draw(parent,list,mdir)
for i = 1:size(list,1)
    TR = stlread([mdir list{i,1} '.stl']);
    patch(parent,'Faces',TR.ConnectivityList,'Vertices',TR.Points,'FaceColor',list{i,2},'EdgeColor','none','FaceLighting','gouraud');
end
end
