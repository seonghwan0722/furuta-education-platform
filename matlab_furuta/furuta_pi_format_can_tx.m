function furuta_pi_format_can_tx(tx)
% Match the Raspberry Pi CAN Transmit raw payload input (8-by-1 uint8).
parent = get_param(tx,'Parent');
ports = get_param(tx,'PortHandles');
line = get_param(ports.Inport(1),'Line');
assert(line~=-1,'Connect the CAN payload before formatting it.');
src = get_param(line,'SrcPortHandle');
srcBlock = get_param(src,'Parent');
if strcmp(get_param(srcBlock,'BlockType'),'Reshape') && ...
        strcmp(get_param(srcBlock,'OutputDimensionality'),'Customize') && ...
        strcmp(get_param(srcBlock,'OutputDimensions'),'[8 1]')
    return
end
p = get_param(tx,'Position');
s = get_param(srcBlock,'Position');
shift = max(0,s(3)+110-p(1));
if shift>0
    p = p+[shift 0 shift 0];
    set_param(tx,'Position',p);
end
y = round((p(2)+p(4))/2);
reshapeBlock = add_block('simulink/Math Operations/Reshape',[parent '/CAN payload 8x1'], ...
    'MakeNameUnique','on','Position',[p(1)-94 y-16 p(1)-23 y+16], ...
    'OutputDimensionality','Customize','OutputDimensions','[8 1]');
r = get_param(reshapeBlock,'PortHandles');
delete_line(line);
add_line(parent,src,r.Inport,'autorouting','on');
add_line(parent,r.Outport,ports.Inport(1),'autorouting','on');
end
