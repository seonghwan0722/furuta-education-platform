function x0 = sp_sample_x0(n,mix,bank)
% mix = [bottom upright bank uniform] fractions.
cp = cumsum(mix(:)'/sum(mix)); k = 1+sum(rand(n,1)>cp,2)'; k = min(k,4);
x0 = zeros(4,n);
for j=1:n
    switch k(j)
        case 1 % hanging, near rest
            x0(:,j)=[pi*(2*rand-1); pi+deg2rad(25)*(2*rand-1); 1.0*(2*rand-1); 1.5*(2*rand-1)];
        case 2 % near upright
            x0(:,j)=[pi*(2*rand-1); deg2rad(15)*(2*rand-1); 2*(2*rand-1); 1.5*(2*rand-1)];
        case 3 % expert trajectory state with noise
            s=bank(:,randi(size(bank,2)));
            x0(:,j)=s+[0.2;0.05;0.3;0.3].*randn(4,1);
        case 4 % broad
            x0(:,j)=[pi*(2*rand-1); pi*(2*rand-1); 4*(2*rand-1); 6*(2*rand-1)];
    end
end
end
