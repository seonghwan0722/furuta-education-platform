function add_furuta_plant_blocks(model,name,position)
% 순수 Simulink 블록으로 10 ms RK4 플랜트의 계층을 만든다.
plant = subsystem(model,name,position);
port(plant,'state',1,25,65);
port(plant,'total torque',2,25,162);
outport(plant,'next state',1,785,65);
source = 'state/1';
for j = 1:5
    step = sprintf('Substep %d',j);
    left = 105+135*(j-1);
    pos = [left 40 left+85 112];
    if j == 1
        first = subsystem(plant,step,pos);
        rk4_substep(first);
    else
        add_block(first,[plant '/' step],'Position',pos);
    end
    wire(plant,source,[step '/1']);
    wire(plant,'total torque/1',[step '/2']);
    source = [step '/1'];
end
wire(plant,source,'next state/1');
end

function rk4_substep(sys)
% k1, k2, k3, k4를 각각 동일한 운동방정식 서브시스템으로 계산한다.
port(sys,'x',1,25,45);
port(sys,'tau',2,25,350);
outport(sys,'x next',1,975,45);
base = 'x/1';
for j = 1:4
    stage = sprintf('k%d',j);
    left = 95+175*(j-1);
    pos = [left 155 left+83 207];
    if j == 1
        rhs = subsystem(sys,stage,pos);
        dynamics(rhs);
    else
        add_block(rhs,[sys '/' stage],'Position',pos);
    end
    wire(sys,base,[stage '/1']);
    wire(sys,'tau/1',[stage '/2']);
    if j < 4
        scale = sprintf('Stage increment %d',j);
        sumName = sprintf('Stage state %d',j+1);
        factor = 'integrationStep/2';
        if j == 3
            factor = 'integrationStep';
        end
        add(sys,'Math Operations/Gain',scale,[left+88 155 left+136 185],'Gain',factor);
        add(sys,'Math Operations/Sum',sumName,[left+145 99 left+169 126],'Inputs','++');
        wire(sys,[stage '/1'],[scale '/1']);
        wire(sys,'x/1',[sumName '/1']);
        wire(sys,[scale '/1'],[sumName '/2']);
        base = [sumName '/1'];
    end
    add(sys,'Math Operations/Gain',sprintf('Weight k%d',j), ...
        [left 256 left+53 286],'Gain',num2str(1+(j==2 || j==3)));
    wire(sys,[stage '/1'],sprintf('Weight k%d/1',j));
end
add(sys,'Math Operations/Sum','Weighted slopes',[774 235 802 310],'Inputs','++++');
add(sys,'Math Operations/Gain','h over 6',[830 250 886 282],'Gain','integrationStep/6');
add(sys,'Math Operations/Sum','State update',[913 29 943 62],'Inputs','++');
for j = 1:4
    wire(sys,sprintf('Weight k%d/1',j),sprintf('Weighted slopes/%d',j));
end
wire(sys,'Weighted slopes/1','h over 6/1');
wire(sys,'h over 6/1','State update/2');
wire(sys,'x/1','State update/1');
wire(sys,'State update/1','x next/1');
end

function dynamics(sys)
% xdot = [phid; thetad; phidd; thetadd]. 2×2 관성 행렬을 스칼라 식으로 푼다.
port(sys,'x',1,23,56);
port(sys,'tau',2,23,123);
outport(sys,'xdot',1,848,141);
add(sys,'Sources/Constant','Physical parameters',[20 163 89 191], ...
    'Value','plantCoefficients','VectorParams1D','on');
add(sys,'Signal Routing/Mux','State torque parameters',[112 49 120 193],'Inputs','3');
wire(sys,'x/1','State torque parameters/1');
wire(sys,'tau/1','State torque parameters/2');
wire(sys,'Physical parameters/1','State torque parameters/3');

% Mux 순서: phi theta phid thetad tau alpha beta beta2 gam delta eta_phi eta_theta coulomb
expressions = {
    'D11',             'u(6)+u(7)*(sin(u(2))*sin(u(2)))'
    'D12',             'u(9)*cos(u(2))'
    'D22',             'u(8)'
    'Torque RHS arm',  'u(5)-2*u(7)*sin(u(2))*cos(u(2))*u(3)*u(4)+u(9)*sin(u(2))*(u(4)*u(4))-u(11)*u(3)-u(13)*sgn(u(3))'
    'Torque RHS pend', 'u(7)*sin(u(2))*cos(u(2))*(u(3)*u(3))-u(12)*u(4)+u(10)*sin(u(2))'
    'Arm rate',        'u(3)'
    'Pend rate',       'u(4)'};
add(sys,'Signal Routing/Mux','Mass matrix and RHS',[425 49 433 242],'Inputs','5');
add(sys,'Signal Routing/Mux','State derivative',[763 93 771 260],'Inputs','4');
for j = 1:size(expressions,1)
    name = expressions{j,1};
    top = 25+49*(j-1);
    fcn(sys,name,[196 top 351 top+29],expressions{j,2});
    wire(sys,'State torque parameters/1',[name '/1']);
    if j <= 5
        wire(sys,[name '/1'],sprintf('Mass matrix and RHS/%d',j));
    else
        wire(sys,[name '/1'],sprintf('State derivative/%d',j-5));
    end
end
fcn(sys,'Arm acceleration',[496 108 681 144], ...
    '(u(3)*u(4)-u(2)*u(5))/(u(1)*u(3)-(u(2)*u(2)))');
fcn(sys,'Pend acceleration',[496 167 681 203], ...
    '(u(1)*u(5)-u(2)*u(4))/(u(1)*u(3)-(u(2)*u(2)))');
wire(sys,'Mass matrix and RHS/1','Arm acceleration/1');
wire(sys,'Mass matrix and RHS/1','Pend acceleration/1');
wire(sys,'Arm acceleration/1','State derivative/3');
wire(sys,'Pend acceleration/1','State derivative/4');
wire(sys,'State derivative/1','xdot/1');
end

function path = subsystem(parent,name,pos)
path = [parent '/' name];
add_block('built-in/SubSystem',path,'Position',pos);
Simulink.SubSystem.deleteContents(path);
end

function port(sys,name,number,x,y)
add_block('built-in/Inport',[sys '/' name],'Port',num2str(number),'Position',[x y x+29 y+16]);
end

function outport(sys,name,number,x,y)
add_block('built-in/Outport',[sys '/' name],'Port',num2str(number),'Position',[x y x+29 y+16]);
end

function add(sys,lib,name,pos,varargin)
add_block(['simulink/' lib],[sys '/' name],'Position',pos,varargin{:});
end

function fcn(sys,name,pos,expr)
add(sys,'User-Defined Functions/Fcn',name,pos,'Expr',expr);
end

function wire(sys,src,dst)
add_line(sys,src,dst,'autorouting','on');
end
