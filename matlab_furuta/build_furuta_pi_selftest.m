function file = build_furuta_pi_selftest
% Host-only functional checks with no Raspberry Pi I/O.
root = fileparts(mfilename('fullpath'));
mdl = 'furuta_pi_function_check';
file = fullfile(root,[mdl '.slx']);
if bdIsLoaded(mdl)
    assert(strcmp(get_param(mdl,'Dirty'),'off'),'Save or close the open model first.');
    close_system(mdl,0);
end
new_system(mdl);
cleanup = onCleanup(@() close_system(mdl,0));
set_param(mdl,'Solver','FixedStepDiscrete','FixedStep','.01','StopTime','.05');
add_block('simulink/Sources/Digital Clock',[mdl '/Test clock'], ...
    'SampleTime','.01','Position',[30 100 90 130]);
chart('Test sequence',[150 60 285 180],[
    "function [n,arm,rx,action,enable] = cases(t)"
    "n = min(5,round(t/.01));"
    "arm = uint8([146 0 0 0 87 174 255 255]);"
    "rx = n~=3;"
    "action = 1-2*double(n==2);"
    "enable = n~=0;"
    "end"]);
chart('Furuta blocks under test',[365 60 545 200],[
    "function [packet,send,actual,valid] = test(arm,rx,a,enable)"
    "[o,valid] = furuta_pi_decode(arm,rx,uint8(32),uint8([15 219]),[-209.05 -1 4058.5 1],.01);"
    "[packet,send,actual] = furuta_pi_frame(a,o,valid,enable,1,1,.1,ones(1,4),0,1);"
    "end"]);
chart('Compare with expected',[635 70 795 210],[
    "function [pass,row] = compare(n,packet,send,actual,valid)"
    "expectedOpcode = uint8([0 161 161 128 128 128]);"
    "expectedLow = uint8([0 10 246 0 0 0]);"
    "expectedHigh = uint8([0 0 255 0 0 0]);"
    "expectedAction = [0 .1 -.1 0 0 0];"
    "expectedValid = [false true true false false true];"
    "i = n+1;"
    "expected = [expectedOpcode(i) 0 0 0 expectedLow(i) expectedHigh(i) 0 0];"
    "pass = all(packet==expected) && send==(n~=0) && actual==expectedAction(i) && valid==expectedValid(i);"
    "row = [n;double(pass);double(packet(1));actual;double(valid)];"
    "end"]);
add_block('simulink/Model Verification/Assertion',[mdl '/Assert each case'], ...
    'Position',[875 80 935 110]);
add_block('simulink/Sinks/Display',[mdl '/Case result'], ...
    'Position',[875 138 1000 253]);
wire('Test clock/1','Test sequence/1');
wire('Test sequence/1','Compare with expected/1');
for k=1:4
    wire(sprintf('Test sequence/%d',k+1),sprintf('Furuta blocks under test/%d',k));
    wire(sprintf('Furuta blocks under test/%d',k),sprintf('Compare with expected/%d',k+1));
end
wire('Compare with expected/1','Assert each case/1');
h = wire('Compare with expected/2','Case result/1');
set_param(h,'Name','furutaFunctionCheck');
p = get_param([mdl '/Compare with expected'],'PortHandles');
set_param(p.Outport(2),'DataLogging','on');
set_param(mdl,'SignalLogging','on');
save_system(mdl,file);

    function chart(name,pos,code)
        path = [mdl '/' name];
        add_block('simulink/User-Defined Functions/MATLAB Function',path,'Position',pos);
        r = sfroot;
        c = r.find('-isa','Stateflow.EMChart','Path',path);
        c.Script = char(join(code,newline));
    end

    function h = wire(from,to)
        h = add_line(mdl,from,to,'autorouting','on');
    end
end
