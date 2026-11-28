(function(PS){
  'use strict';
  const $=id=>document.getElementById(id),L=PS.ControlLab;
  const fields=['p','i','d','qAngle','qArm','r','horizon','angle','limit','disturbance','plant','antiWindup'];
  const colors=['#3b6de4','#c2410c','#137b64','#8e44ad','#85631b','#465669'];
  const lessons={
    pid:{title:'PID · 오차를 세 가지로 보기',text:'P는 지금의 오차, I는 쌓인 오차, D는 오차가 바뀌는 빠르기를 봅니다. 팔이 멀리 떠나지 않도록 팔 피드백도 함께 사용합니다.',rule:'모터 힘 = P + I + D + 팔 피드백',mission:'P만 쓸 때와 D를 더할 때',steps:['처음 기울기를 5°로 두고 「P만 보기」를 실행하세요.','「P + D」를 누르고 같은 조건에서 다시 실행하세요.','기울기 그래프와 힘 상한 도달 비율을 비교하세요. I를 더한 결과도 예상해 보세요.'],question:'D가 주로 살펴보는 것은?',answers:['오차가 변하는 빠르기','지금까지 쌓인 오차','앞으로 20칸의 경로'],correct:0,why:'D는 오차의 변화 속도를 봅니다. 목표가 고정이면 기울어지는 속도에 반응합니다.',formula:'u = −kp·e − ki·Σ(eΔt) − kd·ωp − kθ·θ − kω·ωa. 목표는 직립 0°이며, D는 측정 속도를 사용합니다.'},
    lqr:{title:'LQR · 무엇을 더 중요하게 볼까?',text:'진자를 세우고 팔을 제자리로 돌리면서 모터 힘도 아끼도록 기준을 정합니다. 모델과 기준으로 상태 피드백 게인을 계산합니다.',rule:'Q: 오차를 줄이기 / R: 힘을 아끼기',mission:'힘을 아끼면 어떤 일이 생길까?',steps:['기본값에서 한 번 실행해 기준 기록을 만드세요.','R만 1에서 10으로 바꾸고 결과를 예상하세요.','평균 오차와 모터 힘 RMS를 함께 비교하세요. 어떤 절충이 생겼나요?'],question:'R을 크게 두는 의미는?',answers:['모터 힘 사용에 더 큰 비용을 준다','진자 질량을 늘린다','신경망 학습 횟수를 늘린다'],correct:0,why:'R은 입력에 주는 비용입니다. 오차와 힘 사이의 절충을 바꾸지만 결과가 항상 좋아지는 것은 아닙니다.',formula:'J = Σ(xᵀQx + Ru²), u = −Kx. Q = diag(Qarm, Qangle, 0.3, 1). 이산 Riccati 방정식으로 K를 계산합니다.'},
    lmpc:{title:'LMPC · 앞을 보고 첫 행동만 쓰기',text:'선형 모델로 앞으로의 기울기를 예측합니다. 힘의 상한을 지키는 명령 계획을 찾고, 첫 명령만 실행한 뒤 현재 상태로 다시 계획합니다.',rule:'예측 → 힘 제한 안에서 계획 → 첫 명령 → 다시 예측',mission:'예측 길이와 힘의 한계',steps:['처음 기울기 10°, 힘 상한 40%에서 실행하세요.','앞을 보는 칸 수를 5와 30으로 바꿔 비교하세요.','다음에는 힘 상한만 20%로 줄이세요. 예측을 길게 해도 힘이 부족하면 어떻게 될까요?'],question:'계획한 명령 중 실제로 적용하는 것은?',answers:['첫 명령 한 개, 이후 다시 계산','계획 전체를 마지막까지 고정','입력 상한을 넘는 명령'],correct:0,why:'MPC는 매 주기 현재 상태에서 다시 풉니다. 미래 계획은 예상이며 실제 움직임을 보장하지 않습니다.',formula:'min Σ(xᵀQx + Ru²) + xNᵀPxN, x(k+1)=Ax(k)+Bu(k), |u(k)|≤상한. N칸 QP를 풀고 u(0)만 적용합니다.'}
  };
  let lessonBridge=null;
  let method='pid',running=false,timer=null,current=null,records=[],selected=new Set(),seq=0;
  let target='sim',kit={connected:false,capable:false,busy:false,checked:false},kitBusy=false,kitRunId=null,stopPending=false;
  let requestSeq=0,runSeq=0,controlMeta=new Map(),hardwarePhase='preparing';
  const requests=new Map(),bridgeAvailable=window.parent!==window;
  const levelPanel=new PS.ImuLevelPanel($('controlLevelPanel'),{compact:true,onState(info){
    const short={ready:'목표 충족',settling:'유지 확인 중',adjust:'조정 필요',moving:'움직임 감지',paused:'측정 일시 정지',disconnected:'연결 대기',waiting:'측정 대기',unsupported:'업데이트 필요',unavailable:'센서 확인 필요',stale:'수신 멈춤'};
    $('controlLevelSummary').textContent=(info.fake?'가상 · ':'')+(info.tilt!==null?info.tilt.toFixed(1)+'° · ':'')+(short[info.state]||'센서 확인 필요');
    $('controlLevelDisclosure').dataset.state=info.state;
  }});
  const endLabels={done:'완료',stop:'사용자 정지',link:'연결 끊김',check:'시작 점검 실패',watchdog:'모터 응답 없음',arm_speed:'팔 속도 제한',pend_speed:'진자 속도 제한',spin:'연속 회전 감지',hot:'모터 온도 제한',tilt:'받침 기울기 초과',level:'영점 측정 실패',not_still:'아래 자세 대기 종료',not_upright:'직립 자세 대기 종료',upright:'직립 범위 이탈',angle:'직립 범위 이탈',deadline:'계산 시간 초과',solver:'계산 수렴 실패',error:'실행 오류',cancelled:'시작 취소',nocapture:'전환 조건 미도달',balance_range:'직립 유지 범위 이탈',controller:'제어기 계산 오류',qp:'최적화 계산 실패',sensor:'센서 응답 이상',nocontrol:'전송된 제어기 없음'};
  let notes={pid:{},lqr:{},lmpc:{}};
  try{const v=JSON.parse(localStorage.getItem('ps-control-notes-v1')||'null');if(v&&typeof v==='object')for(const m of Object.keys(notes))for(const k of ['predict','observe','explain'])if(typeof v[m]?.[k]==='string')notes[m][k]=v[m][k].slice(0,1000);}catch(_){ }
  const angleChart=new PS.Chart($('angleChart'),{xlabel:'초',digits:1});
  const actionChart=new PS.Chart($('actionChart'),{xlabel:'초',digits:2,ymin:-1,ymax:1});
  const predChart=new PS.Chart($('predictionChart'),{xlabel:'앞으로 (초)',digits:1});
  function setText(id,text){const el=$(id);if(el)el.textContent=text;}
  const finite=v=>typeof v==='number'&&Number.isFinite(v);
  const format=(v,digits,suffix='')=>finite(v)?v.toFixed(digits)+suffix:'—';
  function sourceName(o){return o.source==='kit'?(o.fake?'가상 키트':'실제 키트'):o.hybrid?'보정 · 스윙업':o.plant==='ideal'?'원리':'보정';}
  function describe(o){return o.method.toUpperCase()+' · '+(o.source==='kit'||o.hybrid?'아래 자세 → 직립':o.angle+'°')+' · 상한 '+Math.round(o.limit*100)+'% · '+(o.source==='kit'?sourceName(o):o.hybrid?'실물 보정 모델':o.plant==='ideal'?'원리 보기':'실물 보정 모델');}
  function hybridSelected(){return $('startMode').value==='swingup';}
  function requestKit(action,payload,timeout=12000){
    if(!bridgeAvailable)return Promise.reject(Error('설치한 앱의 제어실험실에서 키트를 연결해 주세요.'));
    const id='control-request-'+Date.now()+'-'+(++requestSeq);
    return new Promise((resolve,reject)=>{
      const timer=setTimeout(()=>{requests.delete(id);const error=Error('앱의 응답이 없습니다. 연결 상태를 확인해 주세요.');error.transportTimeout=true;reject(error);},timeout);
      requests.set(id,{resolve,reject,timer});
      window.parent.postMessage({type:'control-kit-request',id,action,payload:payload||{}},'*');
    });
  }
  function paintKit(){
    $('kitControl').hidden=target!=='kit';
    levelPanel.update(kit.imu,kit.connected,kit.busy||kitBusy);
    if(kit.busy||kitBusy||running)$('controlLevelDisclosure').open=false;
    $('targetSim').setAttribute('aria-pressed',String(target==='sim'));
    $('targetKit').setAttribute('aria-pressed',String(target==='kit'));
    const label=!bridgeAvailable?'메인 앱에서 열어 주세요':!kit.connected?'키트 연결 필요':!kit.capable?'Pi 프로그램 업데이트 필요':(kit.fake?'가상 키트 · ':'')+(kit.checked?'점검 완료':'연결됨 · 점검 필요');
    setText('kitConnection',label);
    setText('kitConnectionNote',!bridgeAvailable?'이 화면을 단독으로 열면 실물 연결을 사용할 수 없습니다.':!kit.connected?'키트 연결하기에서 Pi 포트를 선택하세요.':!kit.capable?'연결된 Pi에 PID·LQR·LMPC 수신 기능이 없습니다. 최신 수신기를 설치해 주세요.':(kit.name||'진자 키트')+' · '+(kit.port||'USB')+' · '+(kit.busy?'키트 사용 중':'50 Hz 내부 제어'));
    $('connectKit').disabled=running||kitBusy||kit.busy||!bridgeAvailable;
    $('checkKit').disabled=running||kitBusy||kit.busy||!kit.connected||!kit.capable;
    $('targetSim').disabled=$('targetKit').disabled=running||kitBusy;
    $('compare').disabled=running||kitBusy||target==='kit';
    $('run').disabled=running||kitBusy||(target==='kit'&&(!kit.connected||!kit.capable||!kit.checked||kit.busy));
    $('run').textContent=target==='kit'?(kit.fake?'▶ 가상 키트 시작':'▶ 실제 키트 시작'):'▶ 시작하기';
    $('back').disabled=running||kitBusy;
    $('speed').disabled=running||target==='kit';
    $('speedField').hidden=target==='kit';
    $('startMode').disabled=running||kitBusy||target==='kit';
    for(const k of ['angle','disturbance','plant'])$(k).disabled=running||kitBusy||target==='kit'||hybridSelected();
    $('angle').closest('.numberField').classList.toggle('simulationOnly',target==='kit'||hybridSelected());
    setText('simulationOnlyNote',target==='kit'?'처음 기울기·흔들기·모델 선택은 시뮬레이션 전용입니다. 실물은 아래 자세에서 스윙업합니다.':'세 방법을 비교할 때 같은 조건을 씁니다.');
    setText('startModeNote',target==='kit'?'실물은 수평 측정 후 자동 스윙업을 수행합니다.':hybridSelected()?'실물 보정 모델에서 아래 자세로 시작합니다. 초기각·외란 설정을 사용하지 않습니다. 후보 전환 조건: 직립 오차 5°·진자 속도 0.2 rad/s·팔 속도 4 rad/s 이내. 실물 성공이 검증된 범위는 아닙니다.':'직립 근처에서 제어기 원리를 비교합니다.');
  }
  function setTarget(value){if(running||kitBusy)return;target=value;outputs();paintKit();resultContext();if(!current)paint(null);}
  function hardwareExperiment(o,config){
    const rows=[],actual=Object.assign({},o,{source:'kit',plant:'hardware',fake:!!kit.fake,angle:null,disturbance:0});
    let status='준비 중',ended=false,endInfo=null;
    return {o:actual,config,rows,sim:null,ctrl:{last:{}},saved:false,
      end(info){ended=true;endInfo=info;status=endLabels[info.reason]||info.reason||'실행 종료';},
      done:()=>ended,
      summary(){
        let sumError=0,sumU=0,sat=0,known=0,maxU=0,held=0,longest=0,previous=null,balanceError=0,balanceSamples=0;
        for(const row of rows){sumError+=Math.abs(row.error);sumU+=row.u*row.u;maxU=Math.max(maxU,Math.abs(row.u));
          if(row.phase==='balance'){balanceError+=Math.abs(row.error);balanceSamples++;}
          if(finite(row.requested)){known++;if(Math.abs(row.requested)>=actual.limit-1e-8)sat++;}
          const elapsed=previous===null?0:Math.max(0,Math.min(.1,row.t-previous));previous=row.t;
          held=Math.abs(row.error)<=5&&Math.abs(row.pendRate)<=.5?held+elapsed:0;longest=Math.max(longest,held);
        }
        return {method:actual.method,plant:'hardware',source:'kit',fake:actual.fake,status,duration:rows.length?rows.at(-1).t:0,
          meanError:rows.length?sumError/rows.length:null,rmsAction:rows.length?Math.sqrt(sumU/rows.length):null,
          maxAction:rows.length?maxU:null,saturation:known?100*sat/known:null,saturationSamples:known,longest,qpFailures:null,
          balanceMeanError:balanceSamples?balanceError/balanceSamples:null,balanceSamples,
          captureTime:rows.find(row=>row.phase==='balance')?.t??null,
          controllerCrc:this.controllerCrc||null,
          startObservedDeg:rows.length?rows[0].error:null,parameters:Object.assign({},actual),controllerConfig:config,
          limits:{tauMaxNm:2.52,currentMaxA:1.2,armSpeedDps:1100,pendSpeedRadS:25},endInfo};
      }
    };
  }
  function showHardwareMeta(meta){
    if(!current||current.o.source!=='kit'||!meta||!finite(meta.t_ms))return;
    controlMeta.set(Math.round(meta.t_ms),meta);
    while(controlMeta.size>200)controlMeta.delete(controlMeta.keys().next().value);
    current.ctrl.last=meta;
  }
  function showHardwareState(s){
    if(!current||current.o.source!=='kit'||!s||![s.t,s.th,s.al,s.thd,s.ald,s.u].every(finite))return;
    if(current.rows.length&&s.t<=current.rows.at(-1).t)return;
    const meta=controlMeta.get(Math.round(s.t*1000))||{},error=PS.wrap(s.al-Math.PI)*180/Math.PI;
    current.sim={th:s.th,phi:()=>PS.wrap(s.al-Math.PI)};
    current.rows.push({t:s.t,error,arm:s.th*180/Math.PI,armRate:s.thd,pendRate:s.ald,u:s.u,tau:s.u*2.52,
      requested:finite(meta.requested)?meta.requested:null,limited:finite(meta.u)?meta.u:null,
      computeMs:finite(meta.compute_ms)?meta.compute_ms:null,qpResidual:finite(meta.qp_residual)?meta.qp_residual:null,
      qpIterations:finite(meta.iterations)?meta.iterations:null,flags:s.flags,phase:typeof meta.phase==='string'?meta.phase:hardwarePhase});
    display();
  }
  function hardwareMessage(data){
    const code=typeof data==='string'?data:data?.code;
    const args=data?.args||data?.values||[];
    if(code==='swingup'||code==='balance')hardwarePhase=code;
    const labels={upload:'제어 설정을 Pi에 보내는 중',check:'모터·센서 시작 점검 중',still:'진자가 아래로 멈추기를 기다리는 중',brake:'모터 구동 준비 중',level:'받침 수평 측정 중 · 팔이 움직입니다',swingup:'자동 스윙업 중 · 아래 자세에서 진자를 올립니다',balance:method.toUpperCase()+'로 직립 유지 중 · 전환 순간의 팔 위치가 기준입니다',start:'Pi에서 실물 실험 시작',stopping:'정지 완료 응답을 기다리는 중'};
    setText('status',labels[code]||('키트: '+(code||'준비 중')+(Array.isArray(args)&&args.length?' · '+args.join(' '):'')));
    if(code==='start'||code==='swingup'||code==='balance')setText('runState',code==='balance'?'직립 유지 중':code==='swingup'?'스윙업 중':'실물 제어 중');
    else if(!stopPending)setText('runState','실물 준비 중');
  }
  window.addEventListener('message',e=>{
    if(e.source!==window.parent||!e.data)return;
    const m=e.data;
    if(m.type==='control-kit-response'){
      const request=requests.get(m.id);if(!request)return;clearTimeout(request.timer);requests.delete(m.id);
      if(m.ok)request.resolve(m.data);else request.reject(Error(m.error||'키트 요청을 처리하지 못했습니다.'));
      return;
    }
    if(m.type!=='control-kit-event')return;
    if(m.event==='status'){kit=Object.assign({},kit,m.data||{});paintKit();outputs();resultContext();return;}
    if(m.event==='imu'){kit.imu=m.data;levelPanel.update(kit.imu,kit.connected,kit.busy||kitBusy);return;}
    if(!kitRunId||m.runId!==kitRunId)return;
    if(m.event==='message')hardwareMessage(m.data);
    else if(m.event==='control')showHardwareMeta(m.data);
    else if(m.event==='state')showHardwareState(m.data);
    else if(m.event==='end'){
      current.end(m.data||{reason:'error'});const detail=m.data?.detail;
      kitRunId=null;stopPending=false;finish((current.summary().status)+(detail?' · '+detail:''));
      requestKit('status').then(data=>{kit=Object.assign({},kit,data||{});paintKit();}).catch(()=>{});
    }
  });
  function resultContext(){
    const shownMethod=current?current.o.method:method;
    setText('selectedMethod',shownMethod.toUpperCase());
    setText('methodDescription',({pid:'지금·누적·변화',lqr:'균형과 힘의 절충',lmpc:'예측하고 다시 계획'})[shownMethod]);
    setText('resultContext',current?(running?'실행 중: ':'마지막 실험: ')+describe(current.o):'아직 실행한 실험이 없습니다. 설정 탭에서 조건을 정해 보세요.');
    setText('stageSource',(current?current.o.source==='kit':target==='kit')?((current?current.o.fake:kit.fake)?'가상 키트 · 통신 시험':'실제 키트 · 센서 상태'):'PC 시뮬레이션');
    setText('meanLabel',current?.o.source==='kit'||current?.hybrid?'전체 실행 평균 오차':'평균 기울기 오차');
    setText('meanHint',current?.o.source==='kit'||current?.hybrid?'스윙업 구간을 포함합니다.':'얼마나 바르게 서 있었나요?');
    setText('satHint',current?.o.source==='kit'?'수신한 진단 표본에서 계산합니다.':'최대 힘이 얼마나 필요했나요?');
    setText('armReference',current?.hybrid||current?.o.source==='kit'?'팔: 스윙업 시작 / 전환 위치가 0°':'팔: 시작 위치가 0°');
  }
  function openTab(name,focus){
    const tabs=[...document.querySelectorAll('[data-lab-tab]')];
    if(!tabs.some(b=>b.dataset.labTab===name))return;
    for(const b of tabs){const active=b.dataset.labTab===name;b.setAttribute('aria-selected',String(active));b.tabIndex=active?0:-1;if(active&&focus)b.focus();}
    document.querySelectorAll('[data-lab-panel]').forEach(p=>p.hidden=p.dataset.labPanel!==name);
    document.querySelectorAll('.learningFlow [data-open-tab]').forEach(b=>{
      if(b.dataset.openTab===name)b.setAttribute('aria-current','step');
      else b.removeAttribute('aria-current');
    });
    requestAnimationFrame(()=>{graphs();detail();});
  }
  document.querySelectorAll('[data-lab-tab]').forEach(b=>{
    b.addEventListener('click',()=>openTab(b.dataset.labTab));
    b.addEventListener('keydown',e=>{
      const tabs=[...document.querySelectorAll('[data-lab-tab]')];let i=tabs.indexOf(b);
      if(e.key==='ArrowRight')i=(i+1)%tabs.length;
      else if(e.key==='ArrowLeft')i=(i+tabs.length-1)%tabs.length;
      else if(e.key==='Home')i=0;
      else if(e.key==='End')i=tabs.length-1;
      else return;
      e.preventDefault();openTab(tabs[i].dataset.labTab,true);
    });
  });
  document.querySelectorAll('[data-open-tab]').forEach(b=>b.addEventListener('click',()=>openTab(b.dataset.openTab,true)));
  function noteSave(){for(const k of ['predict','observe','explain'])notes[method][k]=$(k).value;try{localStorage.setItem('ps-control-notes-v1',JSON.stringify(notes));}catch(_){ }}
  function read(){const v={method};for(const k of fields)v[k]=$(k).type==='checkbox'?$(k).checked:$(k).value;const o=L.options(v);$('angle').value=o.angle;return o;}
  function makeExperiment(o){
    if(!hybridSelected())return L.experiment(PS.MODEL,o);
    const experiment=L.hybridExperiment(PS.MODEL,o),summarize=experiment.summary;
    experiment.o.hybrid=true;experiment.o.angle=null;
    experiment.summary=function(){
      const summary=summarize(),balance=experiment.rows.filter(row=>row.phase==='balance');
      summary.source='sim';summary.balanceSamples=balance.length;
      summary.balanceMeanError=balance.length?balance.reduce((sum,row)=>sum+Math.abs(row.error),0)/balance.length:null;
      summary.startObservedDeg=experiment.rows.length?experiment.rows[0].error:null;
      return summary;
    };
    return experiment;
  }
  function outputs(){for(const k of fields){const out=document.querySelector('output[for="'+k+'"]');if(out)out.textContent=k==='limit'?Math.round(100*+$(k).value)+'%':k==='horizon'?$(k).value+'칸 · '+(+$(k).value*.02).toFixed(2)+'초':['p','i','d'].includes(k)?(+$(k).value).toFixed(1)+'배':$(k).value;}$('plantNote').textContent=$('plant').value==='ideal'?'같은 rev11 기구에서 쿨롱 마찰·센서 양자화·지연을 끈 원리 실험입니다. 연속 토크와 정확한 상태를 사용합니다.':'기존 앱의 rev11 보정값, 1.2 A 전류 상한·양자화·지연·센서 관측을 그대로 사용합니다. 실물 시험 결과가 아닙니다.';setText('setupSummary',describe({method,angle:$('angle').value,limit:+$('limit').value,plant:target==='sim'&&hybridSelected()?'calibrated':$('plant').value,source:target,fake:target==='kit'&&!!kit.fake,hybrid:target==='sim'&&hybridSelected()}));document.querySelectorAll('[data-preset]').forEach(b=>{const preset=b.dataset.preset;const active=+$('p').value===1&&+$('i').value===(preset==='pid'?.3:0)&&+$('d').value===(preset==='p'?0:1);b.setAttribute('aria-pressed',String(active));});}
  function choose(m){if(running||kitBusy)return;noteSave();method=m;const l=lessons[m];document.querySelectorAll('[data-method]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.method===m)));$('pidSettings').hidden=m!=='pid';$('optimalSettings').hidden=m==='pid';$('mpcSettings').hidden=m!=='lmpc';$('lessonTitle').textContent=l.title;$('lessonText').textContent=l.text;$('rule').textContent=l.rule;$('missionTitle').textContent=l.mission;$('missionSteps').replaceChildren(...l.steps.map(t=>{const e=document.createElement('li');e.textContent=t;return e;}));$('quizQuestion').textContent=l.question;$('quiz').replaceChildren(...l.answers.map((t,i)=>{const b=document.createElement('button');b.textContent=t;b.onclick=()=>{$('feedback').textContent=(i===l.correct?'맞아요. ':'다시 생각해 보세요. ')+l.why;};return b;}));$('feedback').textContent='';$('formula').textContent=l.formula;for(const k of ['predict','observe','explain'])$(k).value=notes[m][k]||'';if(PS.ControlLessons)PS.ControlLessons.show(m);outputs();resultContext();}
  function busy(on){running=on;for(const k of fields)$(k).disabled=on||kitBusy;document.querySelectorAll('[data-method],[data-preset],#resetParams,#run,#compare').forEach(b=>b.disabled=on||kitBusy);$('stop').disabled=!on||stopPending;document.body.classList.toggle('is-running',on);setText('runState',on?(target==='kit'?'실물 준비 중':'실행 중'):current?'실행 종료':'준비');paintKit();resultContext();}
  function paint(sim){
    const c=$('scene'),g=c.getContext('2d'),W=c.width,H=c.height;
    const a=sim?sim.phi():hybridSelected()?Math.PI:+$('angle').value*Math.PI/180,t=sim?sim.th:0;
    const px=W*.25,ax=W*.75,cy=H*.56,rod=Math.min(W*.16,H*.3),arm=Math.min(W*.145,H*.26);
    const tipX=px+rod*Math.sin(a),tipY=cy-rod*Math.cos(a);
    g.clearRect(0,0,W,H);g.fillStyle='#F7F9FB';g.fillRect(0,0,W,H);
    if(!sim&&(current?current.o.source==='kit':target==='kit')){
      g.fillStyle='#51606E';g.font='500 28px Pretendard, "Malgun Gothic", sans-serif';g.textAlign='center';
      g.fillText('실제 센서 상태를 기다리고 있습니다',W/2,H/2);g.textAlign='left';return;
    }
    g.strokeStyle='#D7DEE3';g.lineWidth=2;g.beginPath();g.moveTo(W*.5,24);g.lineTo(W*.5,H-24);g.stroke();
    g.textAlign='left';g.fillStyle='#51606E';g.font='600 28px Pretendard, "Malgun Gothic", sans-serif';
    g.fillText('진자 옆모습',W*.05,36);g.fillText('팔 윗모습',W*.55,36);
    g.font='700 40px Pretendard, "Malgun Gothic", sans-serif';
    g.fillStyle='#3b6de4';g.fillText((a*180/Math.PI).toFixed(1)+'°',W*.05,84);
    g.fillStyle='#C2410C';g.fillText((t*180/Math.PI).toFixed(1)+'°',W*.55,84);
    g.strokeStyle='#B8C6D4';g.lineWidth=2;g.setLineDash([7,7]);g.beginPath();g.moveTo(px,cy-rod-12);g.lineTo(px,cy+24);g.stroke();g.setLineDash([]);
    g.fillStyle='#14212B';g.fillRect(px-48,cy+12,96,16);
    g.strokeStyle='#3b6de4';g.lineWidth=10;g.lineCap='round';g.beginPath();g.moveTo(px,cy);g.lineTo(tipX,tipY);g.stroke();
    g.fillStyle='#3b6de4';g.beginPath();g.arc(tipX,tipY,14,0,2*Math.PI);g.fill();
    g.fillStyle='#14212B';g.beginPath();g.arc(px,cy,11,0,2*Math.PI);g.fill();
    g.strokeStyle='#D7DEE3';g.lineWidth=3;g.beginPath();g.arc(ax,cy,arm,0,2*Math.PI);g.stroke();
    g.strokeStyle='#C2410C';g.lineWidth=10;g.beginPath();g.moveTo(ax,cy);g.lineTo(ax+arm*Math.cos(t),cy-arm*Math.sin(t));g.stroke();
    g.fillStyle='#14212B';g.beginPath();g.arc(ax,cy,11,0,2*Math.PI);g.fill();
    g.fillStyle='#51606E';g.font='24px Pretendard, "Malgun Gothic", sans-serif';g.textAlign='center';
    const captured=(current?.hybrid||current?.o.source==='kit')&&current.rows.at(-1)?.phase==='balance';
    g.fillText('기울기 · 직립이 0°',px,H-20);g.fillText(captured?'회전 각도 · 전환 위치가 0°':'회전 각도 · 시작이 0°',ax,H-20);g.textAlign='left';
  }
  function graphs(){let rs=records.filter(r=>selected.has(r.id));if(current&&!current.saved)rs=rs.concat([{id:0,color:colors[seq%colors.length],result:current.summary(),rows:current.rows}]);const series=key=>rs.map(r=>({name:r.result.method.toUpperCase()+' '+(r.id||'실행'),color:r.color,x:r.rows.map(x=>x.t),y:r.rows.map(x=>x[key])}));angleChart.set(series('error'),10);actionChart.set(series('u'),10);$('chartLegend').replaceChildren(...rs.map(r=>{const chip=document.createElement('span');chip.className='legend-item';const swatch=document.createElement('i');swatch.className='legend-swatch';swatch.style.backgroundColor=r.color;chip.append(swatch,document.createTextNode((r.id?r.id+'회 ':'실행 중 ')+r.result.method.toUpperCase()+' · '+sourceName(r.result)));return chip;}));if(!rs.length)$('chartLegend').textContent='실험을 실행하면 그래프가 나타납니다. 기록을 최대 3개 선택해 비교할 수 있습니다.';}
  function detail(){
    if(!current)return;const l=current.ctrl.last,real=current.o.source==='kit';
    const phase=real?(l.phase||hardwarePhase):current.hybrid?current.summary().phase:'balance';
    $('predictionChart').hidden=real||phase==='swingup'||current.o.method!=='lmpc';$('components').replaceChildren();
    if(phase==='swingup'){
      setText('detailTitle',(real?'Pi의 ':'')+'스윙업 명령');
      setText('detailText','현재는 '+current.o.method.toUpperCase()+' 직립 제어로 전환하기 전입니다. '+(real?'마지막 진단 '+format(finite(l.t_ms)?l.t_ms/1000:null,2,'초')+' · Pi 계산 '+format(l.compute_ms,2,' ms'):'에너지 차이 '+format(l.deficit,4,' J'))+' · 요청 '+format(l.requested,3)+' · 제한 후 '+format(l.u,3)+'.');
    }else if(real){
      setText('detailTitle','Pi가 계산한 '+current.o.method.toUpperCase()+' 명령');
      setText('detailText','마지막 진단 '+format(finite(l.t_ms)?l.t_ms/1000:null,2,'초')+' · Pi 계산 시간 '+format(l.compute_ms,2,' ms')+' · 요청 '+format(l.requested,3)+' · 제어기 제한 후 '+format(l.u,3)+(current.o.method==='lmpc'?' · QP 잔차 '+(finite(l.qp_residual)?l.qp_residual.toExponential(1):'—'):'')+'. 진단은 약 10 Hz로 수신합니다. 그래프의 모터 명령은 전류·제동 제한까지 적용한 값입니다.');
    }else if(current.o.method==='lmpc'){
      setText('detailTitle','LMPC가 지금 예측한 진자 기울기');
      setText('detailText','점선은 선형 모델의 계획입니다. 첫 명령만 적용합니다. QP 잔차: '+(l.qp?l.qp.residual.toExponential(1):'—')+(l.qp&&!l.qp.converged?' (허용 오차 미도달 · 제한 안의 근사해)':''));
      if(l.plan)predChart.set([{name:'예측 (°)',color:'#8e44ad',dash:'5 4',x:l.plan.map((_,i)=>i*.02),y:l.plan.map(x=>x[1]*180/Math.PI)}],current.o.horizon*.02);
    }else{
      setText('detailTitle',current.o.method==='pid'?'P · I · D가 만든 힘':'상태별 피드백이 만든 힘');
      setText('detailText','각 항의 합을 힘의 상한 안으로 제한합니다. 값은 정규화된 모터 명령입니다.');
    }
    if(real||current.hybrid){
      setText('detailText',$('detailText').textContent+' 직립 제어로 전환할 때 팔 각도의 0° 기준이 전환 위치로 바뀝니다.');
      const el=document.createElement('div');el.className='component';el.textContent='직립 제어 구간 평균 오차';
      const value=document.createElement('b');value.textContent=format(current.summary().balanceMeanError,2,'°');el.append(value);$('components').append(el);
    }
    for(const [key,value] of Object.entries(l.parts||{}))if(finite(value)){
      const el=document.createElement('div');el.className='component';el.textContent=({arm:'팔 위치·속도',angle:'진자 기울기',armRate:'팔 속도',pendRate:'진자 속도'})[key]||key;
      const b=document.createElement('b');b.textContent=value.toFixed(3);el.append(b);$('components').append(el);
    }
  }
  function display(){
    if(!current)return;
    const s=current.summary();
    const shown=current.hybrid&&current.rows.length?{th:current.rows.at(-1).arm*Math.PI/180,phi:()=>current.sim.phi()}:current.sim;
    paint(shown);$('clock').textContent=s.duration.toFixed(2)+' / 10.00초';$('mean').textContent=format(s.meanError,2,'°');$('rms').textContent=format(s.rmsAction,3);$('sat').textContent=format(s.saturation,1,'%');if($('runProgress'))$('runProgress').value=s.duration;
    if(running&&current.hybrid){setText('runState',s.phase==='balance'?'직립 유지 모의 중':'스윙업 모의 중');setText('status',s.phase==='balance'?'스윙업에서 '+current.o.method.toUpperCase()+'로 전환 · '+format(s.captureTime,2,'초')+'의 팔 위치가 기준입니다.':'자동 스윙업을 모의하고 있습니다. 후보 조건을 만족하면 선택한 제어기로 전환합니다.');}
    resultContext();graphs();detail();
  }
  function saveRun(status){if(!current||current.saved||(!current.rows.length&&current.o.source!=='kit'))return;const result=current.summary();if(status)result.status=status;current.saved=true;const r={id:++seq,color:colors[(seq-1)%colors.length],result,rows:current.rows.map(x=>Object.assign({},x))};records.push(r);selected.add(r.id);while(selected.size>3)selected.delete(selected.values().next().value);renderRecords();graphs();$('csv').disabled=false;if(lessonBridge)lessonBridge.publish();}
  function renderRecords(){$('records').replaceChildren(...records.slice().reverse().map(r=>{const tr=document.createElement('tr'),td=document.createElement('td'),cb=document.createElement('input');cb.type='checkbox';cb.checked=selected.has(r.id);cb.setAttribute('aria-label',r.id+'회 '+r.result.method+' 비교');cb.onchange=()=>{if(cb.checked){selected.add(r.id);if(selected.size>3)selected.delete(selected.values().next().value);}else selected.delete(r.id);renderRecords();graphs();};td.append(cb);const swatch=document.createElement('i');swatch.className='legend-swatch';swatch.style.backgroundColor=r.color;swatch.setAttribute('aria-hidden','true');td.append(swatch);tr.classList.toggle('selected',selected.has(r.id));tr.append(td);const s=r.result,p=s.parameters;for(const text of [r.id+' '+s.method.toUpperCase()+' / '+sourceName(s),(s.source==='kit'?format(s.startObservedDeg,1,s.fake?'° (가상)':'° (실측)'):s.hybrid?'아래 자세':p.angle+'°')+' / '+Math.round(p.limit*100)+'%',format(s.meanError,2,'°'),format(s.rmsAction,3),s.status+' ('+s.duration.toFixed(1)+'s)']){const cell=document.createElement('td');if(text===s.status+' ('+s.duration.toFixed(1)+'s)'){const badge=document.createElement('span');badge.className='status-badge '+(s.status==='완료'?'complete':'stopped');badge.textContent=s.status;cell.append(badge,document.createTextNode(' '+s.duration.toFixed(1)+'초'));}else cell.textContent=text;tr.append(cell);}return tr;}));setText('recordCount',records.length+'개 기록 · '+selected.size+'개 비교');if($('recordsEmpty'))$('recordsEmpty').hidden=records.length>0;}
  function finish(status){clearTimeout(timer);saveRun(status);busy(false);const s=current?.summary();$('status').textContent=status||((s?.status||'완료')+' · '+(s?.qpFailures?'QP 허용 오차 미도달 '+s.qpFailures+'주기. 결과 해석 시 참고하세요.':'기록에서 다른 시도와 비교해 보세요.'));}
  function canRecord(n){if(records.length+n<=12)return true;$('status').textContent='수업 파일에 제어 시험 12회까지 보관합니다. 상단 돌아가기 후 수업을 저장하고 새 수업을 시작하세요.';return false;}
  function runSimulation(){if(!canRecord(1))return;try{current=makeExperiment(read());}catch(e){$('status').textContent='설정을 확인해 주세요: '+e.message;return;}noteSave();openTab('results');busy(true);$('status').textContent=method.toUpperCase()+' 실험 중 · 입력 설정은 실험 종료 후 바꿀 수 있습니다.';let prev=performance.now(),acc=0;function frame(){const now=performance.now();acc+=Math.min(1.2,(now-prev)/1000)*+$('speed').value;prev=now;try{while(acc>=.02&&!current.done()){current.tick();acc-=.02;}display();}catch(e){finish('계산 오류: '+e.message);return;}if(current.done())finish();else timer=setTimeout(frame,16);}frame();}
  function compare(){if(running||kitBusy||target==='kit'||!canRecord(3))return;let o;try{o=read();}catch(e){$('status').textContent=e.message;return;}noteSave();openTab('results');busy(true);const queue=['pid','lqr','lmpc'];let idx=0;function next(){try{current=makeExperiment(Object.assign({},o,{method:queue[idx]}));}catch(e){finish('계산 오류: '+e.message);return;}function batch(){if(!running)return;try{for(let i=0;i<40&&!current.done();i++)current.tick();display();}catch(e){finish('계산 오류: '+e.message);return;}if(!current.done()){timer=setTimeout(batch,0);return;}saveRun();idx++;if(idx<queue.length){timer=setTimeout(next,0);}else{finish('세 방법 비교 완료 · 같은 시작각·환경·상한으로 실행했습니다. 기본 PD와 LQR은 기준 게인이 같아 결과가 같을 수 있습니다.');}}$('status').textContent=queue[idx].toUpperCase()+' 비교 계산 중…';batch();}next();}
  async function runHardware(){if(!canRecord(1))return;
    if(!kit.connected||!kit.capable||!kit.checked||kit.busy)return;
    let config,o;
    try{o=read();config=L.buildHardwareConfig(PS.MODEL,o);}catch(e){setText('status','제어 설정을 확인해 주세요: '+e.message);return;}
    const runId='control-run-'+Date.now()+'-'+(++runSeq);
    kitRunId=runId;controlMeta.clear();hardwarePhase='preparing';stopPending=false;
    current=hardwareExperiment(o,config);noteSave();openTab('results');busy(true);display();
    setText('status','제어 설정을 Pi에 보내는 중 · 준비 중에도 정지할 수 있습니다.');
    try{
      const out=await requestKit('start',{config,seconds:10,runId},30000);
      if(kitRunId!==runId)return;
      if(out?.runId&&out.runId!==runId){setText('status','실행 응답의 번호가 달라 정지를 요청합니다.');stopRun();return;}
      if(typeof out?.crc==='string')current.controllerCrc=out.crc;
    }catch(e){
      if(kitRunId!==runId)return;
      if(e.transportTimeout){setText('status','시작 응답을 받지 못해 정지를 요청합니다. 종료 확인을 기다립니다.');stopRun();return;}
      current.end({reason:'error',detail:e.message});kitRunId=null;stopPending=false;finish('시작하지 못했습니다: '+e.message);
    }
  }
  async function stopRun(){
    if(!running)return;
    if(current?.o.source!=='kit'){finish('사용자 정지');return;}
    if(stopPending||!kitRunId)return;
    stopPending=true;$('stop').disabled=true;setText('runState','정지 확인 중');setText('status','Pi에 정지를 요청했습니다. 종료 응답을 기다립니다.');
    const runId=kitRunId;
    try{await requestKit('stop',{runId},8000);}
    catch(e){if(kitRunId!==runId)return;stopPending=false;$('stop').disabled=false;setText('status','정지 완료를 확인하지 못했습니다: '+e.message+' · 키트 상태를 확인하세요.');}
  }
  async function kitAction(action){
    if(running||kitBusy)return;kitBusy=true;busy(false);
    setText('status',action==='check'?'모터·센서 응답을 확인합니다. 모터를 움직이지 않습니다.':'키트 연결 창을 엽니다.');
    try{
      const out=await requestKit(action,{},action==='connect'?120000:12000);
      if(action==='check')setText('status',out?.check?.ok===false?'점검 실패: '+(out.check.text||'응답을 확인하세요.'):'점검 응답을 받았습니다. 실물 시작 절차를 확인해 주세요.');
      const status=await requestKit('status');kit=Object.assign({},kit,status||{});
    }catch(e){setText('status',e.message);}
    finally{kitBusy=false;busy(false);}
  }
  $('targetSim').onclick=()=>setTarget('sim');$('targetKit').onclick=()=>setTarget('kit');
  $('startMode').onchange=()=>{if(running||kitBusy)return;outputs();paintKit();if(!current)paint(null);};
  $('connectKit').onclick=()=>kitAction('connect');$('checkKit').onclick=()=>kitAction('check');
  function download(name,text,type){const blob=new Blob([text],{type}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
  $('run').onclick=()=>{if(running||kitBusy)return;if(target==='kit')runHardware();else runSimulation();};$('compare').onclick=compare;$('stop').onclick=stopRun;
  document.querySelectorAll('[data-method]').forEach(b=>b.onclick=()=>choose(b.dataset.method));
  document.querySelectorAll('[data-preset]').forEach(b=>b.onclick=()=>{const k=b.dataset.preset;$('p').value=1;$('i').value=k==='pid'?.3:0;$('d').value=k==='p'?0:1;outputs();});
  for(const k of fields)$(k).addEventListener('input',()=>{outputs();if(!current)paint(null);});
  for(const k of ['predict','observe','explain'])$(k).oninput=noteSave;
  $('resetParams').onclick=()=>{for(const k of fields)if($(k).type==='checkbox')$(k).checked=L.defaults[k];else $(k).value=L.defaults[k];outputs();if(!current)paint(null);};
  $('saveNote').onclick=()=>{noteSave();download('제어실험_학습기록.json',JSON.stringify({version:2,created:new Date().toISOString(),notes,experiments:records},null,2),'application/json');};
  $('csv').onclick=()=>{
    const rows=['run,method,source,fake,plant,start_deg,observed_start_deg,limit,p,i,d,qAngle,qArm,r,horizon,t_s,phase,error_deg,arm_deg,arm_rad_s,pend_rad_s,requested_action,controller_limited_action,applied_action,torque_command_Nm,compute_ms,qp_residual,qp_iterations,flags'];
    for(const record of records){const p=record.result.parameters;for(const x of record.rows)rows.push([record.id,p.method,record.result.source||'sim',!!record.result.fake,p.plant,p.angle,record.result.startObservedDeg??'',p.limit,p.p,p.i,p.d,p.qAngle,p.qArm,p.r,p.horizon,x.t,x.phase||'simulation',x.error,x.arm,x.armRate,x.pendRate,x.requested,x.limited??(record.result.source==='kit'?'':x.u),x.u,x.tau,x.computeMs,x.qpResidual,x.qpIterations,x.flags].map(v=>v==null?'':v).join(','));}
    download('제어실험_기록.csv','\uFEFF'+rows.join('\r\n'),'text/csv;charset=utf-8');
  };
  $('back').onclick=()=>{if(running||kitBusy)return;noteSave();clearTimeout(timer);if(window.parent!==window)window.parent.postMessage({type:'control-lab-close'},'*');else location.href='index.html';};
  window.addEventListener('resize',()=>{graphs();detail();});
  window.addEventListener('beforeunload',()=>{clearTimeout(timer);noteSave();if(kitRunId&&bridgeAvailable)window.parent.postMessage({type:'control-kit-request',id:'control-unload-'+Date.now(),action:'stop',payload:{runId:kitRunId}},'*');});
  for(const k of ['predict','observe','explain'])$(k).value=notes.pid[k]||'';
  choose('pid');paint(null);graphs();renderRecords();resultContext();setText('detailText','실험을 실행하면 제어기가 각 순간의 명령을 어떻게 정했는지 볼 수 있습니다.');openTab('overview');
  paintKit();
  if(bridgeAvailable)requestKit('status').then(data=>{kit=Object.assign({},kit,data||{});paintKit();}).catch(e=>setText('kitConnectionNote',e.message));
  function lessonSnapshot(context){
    if(context?.requested&&(running||kitBusy)){
      const message='진행 중인 실험이 있습니다. 정지한 뒤 닫거나 저장해 주세요.';
      $('status').textContent=message;throw Error(message);
    }
    noteSave();const values={};for(const k of fields.concat(['startMode','speed']))values[k]=$(k).type==='checkbox'?$(k).checked:$(k).value;return {v:1,method,fields:values,notes,records,selected:[...selected]};
  }
  const initialLesson=JSON.parse(JSON.stringify(lessonSnapshot()));
  // Embedded lessons belong to the parent project, not another project's legacy
  // local notes. Standalone control.html keeps its existing notes behavior.
  initialLesson.notes={pid:{},lqr:{},lmpc:{}};
  lessonBridge=window.LessonBridge.register('control',lessonSnapshot,value=>{
    if(running||kitBusy)throw Error('제어 실험을 멈춘 뒤 수업을 불러와 주세요.');
    const s=PS.Classroom.control(value||initialLesson);clearTimeout(timer);current=null;target='sim';kit.checked=false;kitRunId=null;
    for(const k of fields.concat(['startMode','speed'])){if($(k).type==='checkbox')$(k).checked=s.fields[k];else $(k).value=s.fields[k];}
    choose(s.method);for(const m of ['pid','lqr','lmpc'])notes[m]=s.notes[m];for(const k of ['predict','observe','explain'])$(k).value=notes[method][k]||'';
    records=s.records;selected=new Set(s.selected);seq=Math.max(0,...records.map(r=>r.id));renderRecords();graphs();outputs();paint(null);paintKit();resultContext();$('csv').disabled=!records.length;
    $('status').textContent='설정과 기록을 불러왔습니다. 시뮬레이션에서 새 실험을 시작할 수 있습니다.';
  });
})(window.PS);
