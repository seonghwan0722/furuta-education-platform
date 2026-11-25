function scenarios = furuta_scenarios(coulomb)
% 같은 시나리오에서는 모든 제어기에 같은 플랜트와 잡음열을 사용한다.
arguments
    coulomb = 0
end
p = furuta_params; p.coulomb = coulomb;
base = struct('id',"S1",'p',p,'x0',[0;deg2rad(10);0;0], ...
    'duration',5,'pulse',false,'noise',0,'seed',41);
s2 = base; s2.id = "S2"; s2.x0 = zeros(4,1); s2.pulse = true;
s3 = base; s3.id = "S3"; s3.x0(2) = pi; s3.duration = 10;
scenarios = [base s2 s3];
for scale = [.8 1.2]
    for s = [base s2]
        s.id = "S4_"+s.id+"_"+string(round(100*scale));
        for key = ["beta","beta2","gam","delta"]
            s.p.(key) = scale*s.p.(key);
        end
        s.p.eta_phi = 3*s.p.eta_phi;
        s.p.eta_theta = 3*s.p.eta_theta;
        s.noise = deg2rad(.3);
        scenarios(end+1) = s; %#ok<AGROW>
    end
end
end
