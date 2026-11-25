function obj = setopt(obj,name,value)
% 릴리스마다 달라지는 속성을 확인한 뒤 설정한다.
if isprop(obj,name)
    obj.(name) = value;
else
    warning('furuta:MissingOption','%s에 %s 속성이 없습니다.',class(obj),name);
end
end
