/* Inquiry tools reuse the production reward evaluator; no device operations. */
(function(PS){
  'use strict';
  const C=PS.Classroom;
  const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
  const fmt=(n,d=3)=>Number.isFinite(n)?n.toFixed(d):'—';
  PS.ClassroomUI=function(host,h){
    let tab='preview',trace=null,at=-1,traceKey='',selection=['',''];
    const head=el('div',undefined,'inquiry-head');head.append(el('span','직접 바꾸고 · 이유를 설명하기','eyebrow'),el('h2','탐구 실험'));
    const status=el('p');head.append(status);host.append(head);
    const nav=el('div',undefined,'inquiry-tabs'),panels={};host.append(nav);
    for(const [key,title] of [['preview','보상 미리보기'],['mission','수업 미션'],['compare','실험 비교']]){
      const b=el('button',title);b.type='button';b.dataset.inquiry=key;nav.append(b);
      const pane=el('section',undefined,'inquiry-panel');panels[key]=pane;host.append(pane);
      b.onclick=()=>{tab=key;paint();};
    }
    const preview=panels.preview;
    preview.append(el('h3','이 자세에서는 몇 점일까요?'),el('p','슬라이더로 한 순간의 상태를 정해 보세요. 정책을 학습하거나 키트를 움직이지 않고, 현재 규칙의 점수만 계산합니다.','inquiry-note'));
    const workspace=el('div',undefined,'inquiry-work'),visual=el('div',undefined,'inquiry-visual'),controls=el('div',undefined,'inquiry-controls');workspace.append(visual,controls);preview.append(workspace);
    visual.innerHTML='<svg viewBox="0 0 240 190" role="img" aria-label="미리보기 진자 자세"><line x1="120" y1="185" x2="120" y2="20" stroke="#c7cfde" stroke-dasharray="4 4"/><rect x="96" y="105" width="48" height="8" rx="4" fill="#ccd5e5"/><line class="preview-rod" x1="120" y1="160" x2="120" y2="45" stroke="#3b6de4" stroke-width="7" stroke-linecap="round"/><circle class="preview-tip" cx="120" cy="45" r="10" fill="#eea437"/></svg>';
    const score=el('strong','—','preview-score');score.setAttribute('aria-live','polite');visual.append(el('span','이 순간의 보상'),score);
    const inputs={};
    for(const [key,label,min,max,step,value,unit] of [['phi','직립에서 기울기',-180,180,1,0,'°'],['w','진자 각속도',-25,25,.1,0,'rad/s'],['v','팔 각속도',-20,20,.1,0,'rad/s'],['u','모터 지령',-1,1,.01,0,''],['th','팔 각도',-180,180,1,0,'°']]){
      const line=el('label'),caption=el('span',label),out=el('output'),input=el('input');input.type='range';input.min=min;input.max=max;input.step=step;input.value=value;input.id='inquiry-'+key;input.setAttribute('aria-label',label);line.htmlFor=input.id;line.append(caption,out,input);controls.append(line);inputs[key]=input;
      input.oninput=()=>{out.textContent=input.value+' '+unit;calculate(true);};out.textContent=value+' '+unit;
    }
    const problems=el('p',undefined,'inquiry-warning');problems.setAttribute('role','status');preview.append(problems);
    const bars=el('div',undefined,'reward-bars');preview.append(el('h3','어떤 규칙이 점수를 더하고 뺐을까요?'),bars);
    const traceTools=el('div',undefined,'inquiry-actions'),back=el('button','이전'),next=el('button','다음 한 단계'),reset=el('button','처음부터'),focus=el('button','해당 블록 보기');traceTools.append(back,next,reset,focus);
    const traceStatus=el('p'),detail=el('div',undefined,'trace-detail');detail.setAttribute('aria-live','polite');preview.append(el('h3','계산을 한 단계씩 따라가기'),traceTools,traceStatus,detail);
    back.onclick=()=>{at=Math.max(-1,at-1);drawTrace();};next.onclick=()=>{at++;drawTrace();};reset.onclick=()=>{at=-1;drawTrace();};focus.onclick=()=>{const e=trace?.events[at];if(e?.id)h.focus(e.id);};
    function calculate(force){
      const r=h.rule(),values=Object.values(inputs).map(x=>+x.value),key=r.key+'|'+JSON.stringify(h.model().variables)+'|'+values.join(',');
      if(!force&&key===traceKey)return;traceKey=key;at=-1;
      try{trace=r.debug(+inputs.phi.value*Math.PI/180,+inputs.w.value,+inputs.v.value,+inputs.u.value,+inputs.th.value*Math.PI/180);}catch(e){trace={value:0,events:[],issues:[{message:e.message}]};}
      const bad=trace.issues.some(x=>x.level==='error'||!x.level);problems.hidden=!trace.issues.length;problems.textContent=trace.issues.map(x=>x.message).join(' ');score.textContent=bad?'계산 확인 필요':fmt(trace.value);
      const a=+inputs.phi.value*Math.PI/180,x=120+100*Math.sin(a),y=105-75*Math.cos(a);visual.querySelector('line.preview-rod').setAttribute('y1','105');visual.querySelector('line.preview-rod').setAttribute('x2',x);visual.querySelector('line.preview-rod').setAttribute('y2',y);visual.querySelector('circle').setAttribute('cx',x);visual.querySelector('circle').setAttribute('cy',y);
      const grouped=new Map();for(const e of trace.events.filter(e=>e.kind==='score')){const key=e.id||e.label;const old=grouped.get(key)||{label:e.label,value:0,count:0};old.value+=e.value;old.count++;grouped.set(key,old);}
      bars.replaceChildren();const max=Math.max(1,...[...grouped.values()].map(x=>Math.abs(x.value)));
      if(!grouped.size||bad)bars.append(el('p',bad?'계산 오류를 고친 뒤 점수 기여도를 확인하세요.':'실행된 점수 블록이 없습니다.'));
      else for(const row of grouped.values()){const line=el('div',undefined,'reward-bar'),label=el('span',row.label+(row.count>1?' × '+row.count:'')),track=el('div'),fill=el('i');fill.style.width=(100*Math.abs(row.value)/max)+'%';fill.className=row.value<0?'negative':'positive';track.append(fill);line.append(label,track,el('b',fmt(row.value)));bars.append(line);}
      drawTrace();
    }
    function drawTrace(){
      const events=trace?.events||[];at=Math.min(at,events.length-1);back.disabled=at<0;next.disabled=at>=events.length-1;reset.disabled=at<0;const e=events[at];focus.disabled=!e?.id;
      traceStatus.textContent=(at+1)+' / '+events.length+' 단계 · 선택된 조건과 반복 경로만 실행합니다.';
      detail.replaceChildren();if(!e){detail.append(el('p','「다음 한 단계」를 눌러 값 → 조건 → 변수 → 점수 순서를 확인하세요.'));return;}
      const names={value:'값 계산',condition:'조건 판단',variable:'변수 변경',score:'점수 반영',repeat:'반복 횟수',iteration:'반복 시작',control:'흐름 이동',break_loop:'반복 중단',continue_loop:'다음 반복으로'};
      detail.append(el('b',(names[e.kind]||e.kind)+' · '+e.label),el('p','결과 '+(typeof e.value==='boolean'?(e.value?'참':'거짓'):fmt(e.value))+' / 누적 보상 '+fmt(e.total)+(e.loop?' / 반복 '+e.loop+'회차':'')));
      const vars=Object.entries(e.vars||{}).map(([k,v])=>(h.model().variables?.[k]||k)+' = '+fmt(v));detail.append(el('p',vars.length?vars.join(' · '):'아직 대입한 변수가 없습니다.'));
    }
    const mission=panels.mission,select=el('select');select.setAttribute('aria-label','수업 미션');for(const m of C.missions){const o=el('option',m.title);o.value=m.id;select.append(o);}mission.append(select);
    const question=el('h3'),look=el('p'),starter=el('button','이 미션의 시작 규칙 불러오기'),notes={},complete=el('button','미션 정리 완료'),missionState=el('p');missionState.setAttribute('role','status');mission.append(question,look,starter);
    for(const [key,label,placeholder] of [['predict','01 예상','어떤 조건을 바꾸면 무엇이 달라질까요?'],['observe','02 관찰','실험 번호와 그래프에서 확인한 수치를 적어 보세요.'],['explain','03 설명','예상과 결과의 차이를 보상 규칙과 연결해 설명하세요.']]){const wrap=el('label',label);const t=el('textarea');t.maxLength=2000;t.rows=3;t.placeholder=placeholder;t.setAttribute('aria-label',label);wrap.append(t);mission.append(wrap);notes[key]=t;t.oninput=()=>{const state=h.state(),row=state.missions[state.active]||(state.missions[state.active]={runs:[],complete:false});row[key]=t.value;row.complete=false;h.change();paintMissionStatus();};}
    mission.append(complete,missionState);
    select.onchange=()=>{h.state().active=select.value;h.change();paintMission();};
    starter.onclick=()=>{const m=C.missions.find(m=>m.id===h.state().active);if(m.example)h.loadExample(m.example);};
    complete.onclick=()=>{const s=h.state(),m=s.missions[s.active];if(!m||!['predict','observe','explain'].every(k=>m[k]?.trim())||!m.runs?.length){missionState.textContent='예상·관찰·설명을 적고, 이 미션에서 시험을 1회 이상 기록해 주세요.';return;}m.complete=true;h.change();paintMissionStatus();};
    function paintMissionStatus(){const s=h.state(),m=s.missions[s.active];missionState.textContent=(m?.complete?'정리 완료':'탐구 진행 중')+' · 연결한 실험: '+(m?.runs?.length?m.runs.map(n=>n+'회').join(', '):'아직 없음')+' · 완료 표시는 학생의 정리 상태이며 성능 합격 판정이 아닙니다.';}
    function paintMission(){const s=h.state(),m=C.missions.find(m=>m.id===s.active);select.value=m.id;question.textContent=m.question;look.textContent=m.look;starter.hidden=!m.example;starter.disabled=h.busy();complete.disabled=h.busy();for(const k of Object.keys(notes))notes[k].value=s.missions[s.active]?.[k]||'';paintMissionStatus();}
    const compare=panels.compare,selectors=el('div',undefined,'inquiry-actions'),choices=[el('select'),el('select')],comparison=el('div'),csv=el('button','실험 요약 CSV 저장');compare.append(el('h3','조건을 확인하고 결과 비교하기'),el('p','매 시험은 새 기록으로 남습니다. 같은 보상 규칙·모델·시작 조건인지 먼저 확인하세요.','inquiry-note'),selectors,comparison,csv);
    choices.forEach((s,i)=>{s.setAttribute('aria-label',i?'비교 실험 B':'비교 실험 A');selectors.append(s);s.onchange=()=>{const previous=selection[i];selection[i]=s.value;if(selection[1-i]===s.value)selection[1-i]=previous;drawCompare();};});
    function drawCompare(){
      const rows=h.rows();
      for(let i=0;i<2;i++)if(!rows.some(r=>String(r.no)===selection[i]))selection[i]=String(rows[i]?.no||rows[0]?.no||'');
      if(rows.length>1&&selection[0]===selection[1])selection[1]=String(rows.find(r=>String(r.no)!==selection[0]).no);
      choices.forEach((s,i)=>{s.replaceChildren();for(const row of rows){const o=el('option',row.no+'회 · '+(row.label.length>45?row.label.slice(0,45)+'…':row.label));o.value=row.no;s.append(o);}s.value=selection[i];s.disabled=rows.length<2;});csv.disabled=!rows.length;
      comparison.replaceChildren();if(rows.length<2){comparison.append(el('p','서로 다른 두 시험이 쌓이면 비교할 수 있습니다. 같은 정책을 다시 시험해도 새 번호가 생깁니다.'));return;}
      const a=rows.find(r=>String(r.no)===selection[0]),b=rows.find(r=>String(r.no)===selection[1]);if(!a||!b)return;
      const c=C.compare(a,b);comparison.append(el('p',c.compatible?'동일한 시뮬레이션 모델·시작 조건·시험 시간입니다.':'시험 조건이 다르거나 이전 파일입니다. 결과의 단순 순위 비교에 주의하세요.','inquiry-note'),el('p','달라진 항목: '+c.changes.join(', ')));
      const table=el('table'),head=el('tr');for(const t of ['비교 항목',a.no+'회',b.no+'회'])head.append(el('th',t));table.append(head);
      const entries=[['정책 준비',r=>r.snapshot?.learningSource||'이전 기록'],['실행 환경',r=>({sim:'시뮬레이션',kit:'실제 키트',fake:'가상 키트'}[r.snapshot?.source]||'이전 기록')],['규칙',r=>r.label],['학습·시험 조건',r=>{if(!r.snapshot)return '미기록';const o=r.snapshot.options;return (r.snapshot.learningSource.includes('CEM')?o.gens+'세대 · 세대당 '+o.pop+'개 후보 · 변이 '+o.sigma:'SAC 사전 정책 불러오기')+' · 시험 '+r.snapshot.seconds+'초';}],['기록 시간 (s)',r=>fmt(r.analysis?.duration,2)],['직립 조건 만족 합계 (s)',r=>fmt(r.analysis?.uprightSeconds,2)],['첫 0.5초 연속 유지 시작 (s)',r=>fmt(r.analysis?.captureTime,2)],['포착 후 평균 절대오차 (°)',r=>fmt(r.analysis?.postCaptureMAE,2)],['모터 지령 RMS (0~1)',r=>fmt(r.analysis?.rmsAction)]];
      for(const [label,get] of entries){const tr=el('tr');tr.append(el('th',label),el('td',get(a)),el('td',get(b)));table.append(tr);}comparison.append(table,el('p','직립 조건: |오차| ≤ 5°, |진자 각속도| ≤ 0.5 rad/s. 포착은 0.5초 연속 만족으로 정의합니다. 미포착 값은 —로 표시합니다. 지령 RMS는 소비 전력이 아닙니다.','inquiry-note'));
    }
    csv.onclick=()=>{const safe=v=>'"'+String(v??'').replace(/^[=+\-@]/,"'$&").replace(/"/g,'""')+'"';const rows=[['시험','규칙','준비 방식','환경','시간_s','직립합계_s','포착_s','포착후_MAE_deg','지령_RMS'],...h.rows().map(r=>[r.no,r.label,r.snapshot?.learningSource,r.snapshot?.source,r.analysis?.duration,r.analysis?.uprightSeconds,r.analysis?.captureTime,r.analysis?.postCaptureMAE,r.analysis?.rmsAction])];const url=URL.createObjectURL(new Blob(['\ufeff'+rows.map(row=>row.map(safe).join(',')).join('\r\n')],{type:'text/csv;charset=utf-8'}));const a=el('a');a.href=url;a.download='탐구_실험요약.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
    function paint(){nav.querySelectorAll('button').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.inquiry===tab)));for(const k of Object.keys(panels))panels[k].hidden=k!==tab;status.textContent=h.source()+' · 시험은 정책 평가 단계입니다.';calculate(false);paintMission();drawCompare();}
    this.refresh=paint;this.reset=()=>{selection=['',''];traceKey='';paint();};paint();
  };
  PS.LessonSession=function(h){
    let epoch=0,seq=0;const pending=new Map(),ready=new Set(),frames={primer:'primerFrame',control:'controlFrame'};
    const frame=k=>document.getElementById(frames[k]);
    function request(kind,type,state){return new Promise((resolve,reject)=>{const id='lesson-'+(++seq);const timer=setTimeout(()=>{pending.delete(id);reject(Error('수업 화면의 저장 응답이 없습니다. 화면을 다시 열고 저장해 주세요.'));},4000);pending.set(id,{resolve,reject,timer,kind});frame(kind).contentWindow.postMessage({type,kind,epoch,id,state},'*');});}
    window.addEventListener('message',e=>{const d=e.data,k=d?.kind;if(!Object.prototype.hasOwnProperty.call(frames,k)||e.source!==frame(k).contentWindow)return;
      if(d.type==='lesson-ready'){ready.add(k);request(k,'lesson-restore',h.state()[k]).catch(h.error);return;}
      if(d.type!=='lesson-state'||d.epoch!==epoch)return;const p=pending.get(d.id);
      try{if(d.error)throw Error(d.error);h.state()[k]=C[k](d.state);h.change();if(p)p.resolve();}catch(error){if(p)p.reject(error);else h.error(error);}finally{if(p){clearTimeout(p.timer);pending.delete(d.id);}}
    });
    this.capture=async kind=>{if(ready.has(kind))await request(kind,'lesson-snapshot');};
    this.flush=async()=>{await Promise.all([...ready].map(k=>this.capture(k)));};
    this.detach=kind=>ready.delete(kind);
    this.restore=()=>{epoch++;for(const p of pending.values()){clearTimeout(p.timer);p.reject(Error('다른 수업을 불러와 저장 요청을 취소했습니다.'));}pending.clear();for(const k of ready)request(k,'lesson-restore',h.state()[k]).catch(h.error);};
  };
})(window.PS=window.PS||{});
