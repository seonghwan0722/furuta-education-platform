function [F,G] = mpc_prediction(A,B,N)
% x(1:N) = F x(0) + G U.
n = size(A,1);
F = zeros(n*N,n); G = zeros(n*N,N);
for k = 1:N
    rows = (k-1)*n+(1:n);
    F(rows,:) = A^k;
    for j = 1:k
        G(rows,j) = A^(k-j)*B;
    end
end
end
