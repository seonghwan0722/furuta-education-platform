function [summary,records] = evaluate_controllers(controllers,scenarios,plantName,runner,output)
% 제어기별 궤적을 저장하고 시나리오별 비교 그림을 만든다.
arguments
    controllers
    scenarios
    plantName
    runner = @run_scenario
    output = results_dir
end
summary = table; records = struct('controller',{},'scenario',{},'plant',{},'run',{});
for s = scenarios
    f = figure('Visible','off');
    cleanup = onCleanup(@() close(f));
    layout = tiledlayout(f,3,1);
    title(layout,plantName+" / "+s.id);
    ax = [nexttile(layout),nexttile(layout),nexttile(layout)];
    for a = ax
        hold(a,'on'); grid(a,'on');
    end
    for c = controllers
        r = runner(c.fun,s);
        row = addvars(r.metrics,c.name,s.id,plantName,'Before',1, ...
            'NewVariableNames',{'Controller','Scenario','Plant'});
        summary = [summary; row]; %#ok<AGROW>
        records(end+1) = struct('controller',c.name,'scenario',s.id,'plant',plantName,'run',r); %#ok<AGROW>
        plot(ax(1),r.t,rad2deg(wrap_theta(r.x(2,:))),'DisplayName',c.name);
        plot(ax(2),r.t,rad2deg(r.x(1,:)),'DisplayName',c.name);
        stairs(ax(3),r.t,[r.tau r.tau(end)],'DisplayName',c.name);
        if r.metrics.Status ~= "완료" || r.metrics.SaturationRatio>=.999
            fprintf('%s / %s: %s, 포화율 %.3g. 이득, R, 스윙업 kE, 학습률 및 입력 단위를 확인하세요.\n', ...
                c.name,s.id,r.metrics.Status,r.metrics.SaturationRatio);
        elseif isnan(r.metrics.Settle_s)
            fprintf('%s / %s: 미정착. 스윙업 성공 여부, 회복 구간 및 팔 드리프트를 확인하세요.\n',c.name,s.id);
        end
    end
    ylabel(ax(1),'진자 각도 (deg)');
    ylabel(ax(2),'팔 각도 (deg)');
    ylabel(ax(3),'제어 토크 (N·m)');
    xlabel(ax(3),'시간 (s)');
    legend(ax(1),'Location','best','Interpreter','none');
    exportgraphics(f,fullfile(output,plantName+"_"+s.id+".png"));
    clear cleanup
end
end
