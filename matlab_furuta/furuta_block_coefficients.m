function values = furuta_block_coefficients(p)
% 운동방정식 서브시스템의 파라미터 Mux 순서.
values = [p.alpha p.beta p.beta2 p.gam p.delta p.eta_phi p.eta_theta p.coulomb];
end
