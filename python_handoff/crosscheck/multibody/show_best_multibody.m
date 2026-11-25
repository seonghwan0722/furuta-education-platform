% Show the best balancing policy (SAC sac24 ck_0100) in Simscape Multibody with the rev11 CAD meshes.
% 1) closed-loop rollout on the rev11 identified plant with the same Pi pipeline as all evaluations (sp_eval2)
% 2) a new, standalone Multibody model (rev11 STL meshes, two revolute joints driven by that trajectory)
% 3) Mechanics Explorer animation + MP4 via smwritevideo
% Nothing in matlab_furuta is modified; the model is created in this folder.
here = fileparts(mfilename('fullpath')); if isempty(here), here = pwd; end
addpath('C:/Capstone1/matlab_furuta'); addpath('C:/Capstone1/matlab_furuta/swingup_ppo'); addpath('C:/Capstone1/matlab_furuta/rev11');
if ~exist('ckName','var'), ckName = 'sac24_rev11_armrate2/ck_0100'; end
if ~exist('T','var'), T = 12; end
if ~exist('viewTilt','var'), viewTilt = 22; end
if ~exist('viewYaw','var'), viewYaw = -35; end
if ~exist('vidName','var'), vidName = 'sac24_ck0100_multibody_me_iso3'; end
ck = load(['C:/Capstone1/matlab_furuta/results/ppo_swingup_20261119/' ckName '.mat'],'actor');
c = rev11_ident_config();
x0 = [0; pi; 0; 0];                                   % hanging at rest
[M,R] = sp_eval2(ck.actor, x0, T, c, struct('filter',true,'delay',1,'armLim',15,'pendLim',25,'frac',0,'regenBudget',0.8));
disp(M)
t = R.t(:); X = squeeze(R.X); th = X(1,:)'; phi = X(2,:)';
alpha = pi - phi;                                     % MuJoCo/CAD pendulum angle (0 = hanging), see xcheck.py (SP = -1)
save(fullfile(here,'trajectory.mat'),'t','th','alpha','M','ckName');

mdl = 'furuta_rev11_multibody_show';
if bdIsLoaded(mdl), close_system(mdl,0); end
if isfile(fullfile(here,[mdl '.slx'])), delete(fullfile(here,[mdl '.slx'])); end
new_system(mdl); load_system('sm_lib'); load_system('nesl_utility'); load_system('simulink');
L = @(p) regexprep(p,' ',char(32));
lib = @(name) find_system('sm_lib','SearchDepth',2,'Type','block','Name',name);
blk = @(src,name,pos) add_block(src,[mdl '/' name],'Position',pos);
s = lib(sprintf('World\nFrame')); if isempty(s), s = find_system('sm_lib','RegExp','on','SearchDepth',2,'Name','World.Frame'); end
W  = blk(s{1},'World',[20 200 60 240]);
s = find_system('sm_lib','RegExp','on','SearchDepth',2,'Name','Mechanism.Configuration'); MC = blk(s{1},'MechConfig',[20 300 60 340]);
SC = blk('nesl_utility/Solver Configuration','Solver',[20 400 60 440]);
s = find_system('sm_lib','RegExp','on','SearchDepth',2,'Name','Revolute.Joint'); revLib = s{1};
s = find_system('sm_lib','RegExp','on','SearchDepth',2,'Name','Rigid.Transform'); rtLib = s{1};
s = find_system('sm_lib','RegExp','on','SearchDepth',2,'Name','File.Solid'); fsLib = s{1};
set_param(MC,'GravityVector','[0 0 -9.81]');

% meshes per body (same colours as the MuJoCo XML)
mdir = 'C:/Capstone1/sim2real_rev11/sim2real_rev11/rev11_model/meshes/';
base = {'base_print',[.82 .83 .85];'base_logo_blue',[.1 .35 .8];'base_logo_black',[.1 .1 .11];'base_metal',[.74 .76 .79]; ...
        'base_pcb_02420c',[.01 .26 .05];'base_pcb_021105',[.01 .07 .02];'base_other_e8e8d3',[.91 .91 .83];'base_other_af0202',[.69 .01 .01]; ...
        'base_dark',[.12 .12 .14];'base_motor',[.15 .15 .17];'base_brass',[.8 .6 .22];'base_screw_silver',[.78 .79 .82]};
arm  = {'arm_print',[.82 .83 .85];'arm_metal',[.74 .76 .79];'arm_logo_blue',[.1 .35 .8];'arm_logo_black',[.1 .1 .11]; ...
        'arm_pcb_021184',[.01 .07 .52];'arm_pcb_000000',[0 0 0];'arm_pcb_d8d8c9',[.85 .85 .79];'arm_pcb_ededed',[.93 .93 .93]; ...
        'arm_cable',[.75 .1 .1];'arm_screw_silver',[.78 .79 .82]};
pend = {'pend_print',[.95 .55 .15];'pend_magnet',[.4 .1 .3];'pend_tip_screw_black',[.08 .08 .09]};

% joints and frames
RA = blk(revLib,'Arm joint',[200 200 260 260]);
TP = blk(rtLib,'Pendulum hinge (z -> x)',[320 200 380 260]);
set_param(TP,'TranslationMethod','Cartesian','TranslationCartesianOffset','[0 0 0.018]','RotationMethod','StandardAxis','RotationStandardAxis','+Y','RotationAngle','90');
RP = blk(revLib,'Pendulum joint',[440 200 500 260]);
TB = blk(rtLib,'Back to pendulum frame',[560 200 620 260]);
set_param(TB,'RotationMethod','StandardAxis','RotationStandardAxis','+Y','RotationAngle','-90');
for j = [RA RP], set_param(j,'MotionActuationMode','InputMotion','TorqueActuationMode','ComputedTorque'); end
pc = @(h) get_param(h,'PortConnectivity');
P = @(h) get_param(h,'PortHandles');
conn = @(a,ai,b,bi) add_line(mdl, pick(P(a),ai), pick(P(b),bi), 'autorouting','on');

% camera: Mechanics Explorer records its default front view (look along +Y, Z up), so the whole mechanism is
% turned instead (kinematic replay -> gravity direction irrelevant): yaw -35 deg, then tilt the top 22 deg toward the camera.
V1 = blk(rtLib,'View tilt',[80 120 120 160]); set_param(V1,'RotationMethod','StandardAxis','RotationStandardAxis','+X','RotationAngle',num2str(viewTilt));
V2 = blk(rtLib,'View yaw',[130 120 170 160]); set_param(V2,'RotationMethod','StandardAxis','RotationStandardAxis','+Z','RotationAngle',num2str(viewYaw));
conn(W,'R1',V1,'L1'); conn(V1,'R1',V2,'L1');
conn(V2,'R1',RA,'L1'); conn(W,'R1',MC,'R1'); conn(W,'R1',SC,'R1');
conn(RA,'R1',TP,'L1'); conn(TP,'R1',RP,'L1'); conn(RP,'R1',TB,'L1');
% framing markers (tiny, white) so the auto-fit view includes the upright pendulum and full arm sweep
fr = [0 0 0.25; 0 0 -0.21; 0.19 0 0.05; -0.19 0 0.05; 0 0.19 0.05; 0 -0.19 0.05];
for i = 1:size(fr,1)
    tm = blk(rtLib,sprintf('Frame mark %d',i),[700+50*i 450 740+50*i 490]);
    set_param(tm,'TranslationMethod','Cartesian','TranslationCartesianOffset',mat2str(fr(i,:)));
    s = find_system('sm_lib','RegExp','on','SearchDepth',2,'Name','Spherical.Solid');
    if isempty(s), continue; end
    sm = blk(s{1},sprintf('Mark %d',i),[700+50*i 520 740+50*i 560]);
    set_param(sm,'SphereRadius','0.002','InertiaType','PointMass','Mass','1e-6','GraphicDiffuseColor','[1 1 1]','GraphicOpacity','0');
    conn(V2,'R1',tm,'L1'); conn(tm,'R1',sm,'R1');
end
addSolids(mdl,fsLib,base,V2,'R1',[100 500],mdir,P,conn);
addSolids(mdl,fsLib,arm,RA,'R1',[300 500],mdir,P,conn);
addSolids(mdl,fsLib,pend,TB,'R1',[700 200],mdir,P,conn);

% motion inputs
assignin('base','armQ',timeseries(th,t)); assignin('base','pendQ',timeseries(alpha,t));
names = {'armQ','pendQ'}; joints = [RA RP];
for k = 1:2
    fw = add_block('simulink/Sources/From Workspace',[mdl '/' names{k}],'VariableName',names{k},'Interpolate','on','Position',[60 60+70*(k-1) 140 90+70*(k-1)]);
    cv = add_block('nesl_utility/Simulink-PS Converter',[mdl '/' names{k} ' PS'],'Position',[180 60+70*(k-1) 210 90+70*(k-1)]);
    set_param(cv,'FilteringAndDerivatives','filter','SimscapeFilterOrder','2','InputFilterTimeConstant','0.002','Unit','rad');
    add_line(mdl,P(fw).Outport(1),P(cv).Inport(1),'autorouting','on');
    add_line(mdl,P(cv).RConn(1),P(joints(k)).LConn(2),'autorouting','on');
end
set_param(mdl,'StopTime',num2str(t(end)),'Solver','ode23t','MaxStep','0.005','SimMechanicsOpenEditorOnUpdate','on');
save_system(mdl,fullfile(here,[mdl '.slx']));
out = sim(mdl);
fprintf('SIM_DONE %s  T=%.1f s  passed=%d reach=%.2f s\n', ckName, T, M.Passed, M.ReachTime);
try
    smwritevideo(mdl, fullfile(here,vidName), 'PlaybackSpeedRatio',1, 'FrameRate',30, 'VideoFormat','mpeg-4');
    fprintf('VIDEO_DONE %s\n', fullfile(here,'sac24_ck0100_multibody.mp4'));
catch e
    fprintf('VIDEO_FAILED %s\n', e.message);
end

function h = pick(ph, name)
k = str2double(name(2:end));
if name(1) == 'L', h = ph.LConn(k); else, h = ph.RConn(k); end
end
function addSolids(mdl,fsLib,list,frameBlk,port,xy,mdir,P,conn)
for i = 1:size(list,1)
    b = add_block(fsLib,[mdl '/' list{i,1}],'Position',[xy(1)+70*mod(i-1,6) xy(2)+70*floor((i-1)/6) xy(1)+70*mod(i-1,6)+40 xy(2)+70*floor((i-1)/6)+40]);
    set_param(b,'ExtGeomFileName',[mdir list{i,1} '.stl'],'UnitType','Custom','ExtGeomFileUnits','m','InertiaType','PointMass','Mass','1e-3', ...
        'GraphicType','FromGeometry','GraphicVisPropType','SimpleVisualProperties','GraphicDiffuseColor',mat2str(list{i,2}));
    conn(frameBlk,port,b,'R1');
end
end
