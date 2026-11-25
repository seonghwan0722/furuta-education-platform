function plot_rl_history
% 같은 보상 레벨인지 범례에서 확인할 수 있도록 표시한다.
f = figure('Visible','off');
cleanup = onCleanup(@() close(f));
layout = tiledlayout(f,1,2);
ax = [nexttile(layout) nexttile(layout)];
for a = ax
    hold(a,'on'); grid(a,'on');
    ylabel(a,'에피소드 리턴');
end
found = false;
for name = ["PPO","SAC"]
    file = fullfile(results_dir,lower(name)+".mat");
    if isfile(file)
        data = load(file,'history','level','QUICK');
        h = data.history;
        label = sprintf('%s (레벨 %d, QUICK=%d)',name,data.level,data.QUICK);
        plot(ax(1),h.Steps,h.Return,'DisplayName',label);
        plot(ax(2),h.Seconds,h.Return,'DisplayName',label);
        found = true;
    end
end
if found
    xlabel(ax(1),'누적 환경 스텝');
    xlabel(ax(2),'벽시계 시간 (s)');
    legend(ax(1),'Location','best');
    legend(ax(2),'Location','best');
    exportgraphics(f,fullfile(results_dir,'rl_learning.png'));
end
end
