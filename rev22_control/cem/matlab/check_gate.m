% Unit check: cem_gate.m against Python cem.gate on 4000 random (u, v, bal) points (gate_test.csv from cem.py).
g = cem_config(); T = csvread('gate_test.csv');
u = cem_gate(T(:,1)', T(:,2)', T(:,3)' > 0.5, g);
printf('gate: max|u_matlab - u_python| = %.3g over %d points\n', max(abs(u - T(:,4)')), size(T,1));
