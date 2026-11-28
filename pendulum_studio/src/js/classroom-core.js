/* Shared, data-only classroom contracts. No device or controller operations. */
(function (root) {
  'use strict';
  const P = root.PS = root.PS || {};
  const missions = [
    {id:'height',title:'1. 높이만 칭찬하기',example:'높이만',question:'높이만 보상하면 직립에서 멈출까요?',look:'높이 그래프와 직립 유지 시간을 확인하세요.'},
    {id:'upright',title:'2. 직립 보너스 주기',example:'높이 + 서면 보너스',question:'직립 보너스를 더하면 이전 실험과 무엇이 달라질까요?',look:'보너스가 켜지는 조건과 실제 움직임을 연결해 보세요.'},
    {id:'speed',title:'3. 움직임 줄이기',example:'진자 천천히',question:'속도 감점이 너무 크면 세우는 과정에도 영향을 줄까요?',look:'세우기와 직립 유지에 필요한 움직임을 구분하세요.'},
    {id:'effort',title:'4. 힘 아끼기',example:'힘 아끼기',question:'힘 감점을 늘리면 유지 시간과 모터 지령은 어떻게 달라질까요?',look:'모터 지령 RMS는 소비 전력 측정값이 아닙니다.'},
    {id:'design',title:'5. 나만의 규칙 설계',example:null,question:'어떤 행동을 유도할지 정하고, 한 가지 조건을 바꿔 비교해 보세요.',look:'보상 총점과 실제 성공 여부를 따로 설명하세요.'}
  ];
  function fail(s) { throw Error(s); }
  function number(v,min,max,label) { if(typeof v!=='number'||!Number.isFinite(v)||v<min||v>max)fail(label+' 값이 올바르지 않습니다.'); return v; }
  function data(value) {
    let count=0;
    function visit(v,depth) {
      if(++count>2000000||depth>40)fail('수업 기록이 너무 크거나 깊습니다.');
      if(v===null||typeof v==='boolean')return v;
      if(typeof v==='number')return number(v,-Number.MAX_VALUE,Number.MAX_VALUE,'기록');
      if(typeof v==='string'){if(v.length>100000)fail('기록의 문장이 너무 깁니다.');return v;}
      if(Array.isArray(v)){if(v.length>10000)fail('기록 배열이 너무 깁니다.');return v.map(x=>visit(x,depth+1));}
      if(!v||typeof v!=='object')fail('수업 기록 형식을 확인해 주세요.');
      const out={};for(const key of Object.keys(v)){if(['__proto__','constructor','prototype'].includes(key))fail('지원하지 않는 기록 속성입니다.');out[key]=visit(v[key],depth+1);}return out;
    }
    return visit(value,0);
  }
  function empty() { return {v:1,active:'height',missions:{},primer:null,control:null}; }
  function primer(value) {
    if(value===null)return null;
    const x=data(value);if(x.v!==1||!x.grid||!x.bandit)fail('활동 0 기록 버전을 확인해 주세요.');
    const g=x.grid,o=g.opts;
    if(!o||!['maze','risk'].includes(o.map))fail('길찾기 지도를 확인해 주세요.');
    for(const k of ['epsilon','alpha','gamma'])number(o[k],0,1,k);
    number(o.seed,0,4294967295,'난수 시드');number(o.stepReward,-100,100,'이동 보상');number(g.rng,0,4294967295,'난수 상태');
    if(!Number.isInteger(o.seed)||!Number.isInteger(g.rng))fail('난수 상태는 정수여야 합니다.');
    if(!Array.isArray(g.q)||g.q.length!==36||g.q.some(row=>!Array.isArray(row)||row.length!==4))fail('Q표 크기가 올바르지 않습니다.');
    g.q.flat().forEach(v=>number(v,-1e9,1e9,'Q값'));
    if(!Array.isArray(x.history)||x.history.length>5000)fail('길찾기 기록은 5,000회까지 보관합니다.');
    function episode(e){if(!e||!Array.isArray(e.path)||e.path.length<1||e.path.length>81)fail('경로 기록을 확인해 주세요.');e.path.forEach(s=>{number(s,0,35,'격자');if(!Number.isInteger(s))fail('격자 번호는 정수여야 합니다.');});number(e.total,-1e6,1e6,'보상');if(typeof e.goal!=='boolean'||typeof e.reason!=='string')fail('경로 결과를 확인해 주세요.');number(e.steps,0,80,'걸음');}
    x.history.forEach(episode);if(x.bestEpisode){episode(x.bestEpisode.episode);number(x.bestEpisode.number,1,5000,'최고 기록 번호');}
    if(x.history.length&&(!x.bestEpisode||!Number.isInteger(x.bestEpisode.number)||x.bestEpisode.number>x.history.length))fail('최고 기록과 에피소드 번호를 확인해 주세요.');
    const b=x.bandit;
    if(!Array.isArray(b.n)||!Array.isArray(b.q)||b.n.length!==3||b.q.length!==3)fail('자판기 기록을 확인해 주세요.');
    b.n.forEach(n=>{number(n,0,1e9,'선택 횟수');if(!Number.isInteger(n))fail('선택 횟수는 정수여야 합니다.');});b.q.forEach(v=>number(v,0,1,'평균 보상'));
    number(b.total,0,b.n.reduce((a,c)=>a+c,0),'별');number(b.rng,0,4294967295,'난수 상태');
    if(!Number.isInteger(b.total)||!Number.isInteger(b.rng)||!Number.isInteger(x.selected))fail('체험 횟수와 칸 번호는 정수여야 합니다.');
    if(!['basics','grid','bandit','future','bridge','modeling'].includes(x.topic))fail('활동 0 탭을 확인해 주세요.');
    number(x.selected,0,35,'선택 칸');number(x.futureGamma,0,1,'할인율');number(x.banditEpsilon,0,1,'탐험 비율');
    if(!Array.isArray(x.answers)||x.answers.length!==3||x.answers.some((a,i)=>a!==null&&(!Number.isInteger(a)||a<0||a>(i===2?2:1))))fail('이해 확인 기록을 확인해 주세요.');
    return x;
  }
  function control(value) {
    if(value===null)return null;
    const x=data(value);if(x.v!==1||!['pid','lqr','lmpc'].includes(x.method)||!x.fields||!x.notes||!Array.isArray(x.records)||x.records.length>12)fail('제어 실험실 기록 형식을 확인해 주세요.');
    const ranges={p:[0,3],i:[0,3],d:[0,3],qAngle:[1,200],qArm:[.05,10],r:[.1,20],horizon:[5,40],angle:[-30,30],limit:[.05,1]};
    for(const [k,range] of Object.entries(ranges)){if(typeof x.fields[k]!=='string'||!x.fields[k].trim())fail('제어 설정 '+k+'를 확인해 주세요.');number(Number(x.fields[k]),range[0],range[1],k);}
    if(!Number.isInteger(+x.fields.horizon))fail('예측 구간은 정수여야 합니다.');
    for(const [k,choices] of Object.entries({disturbance:['0','0.2','-0.2'],plant:['ideal','calibrated'],startMode:['balance','swingup'],speed:['1','4']}))if(!choices.includes(x.fields[k]))fail('제어 설정 '+k+'를 확인해 주세요.');
    if(typeof x.fields.antiWindup!=='boolean')fail('누적 제한 설정을 확인해 주세요.');
    for(const m of ['pid','lqr','lmpc']){if(!x.notes[m])x.notes[m]={};for(const k of ['predict','observe','explain']){const s=x.notes[m][k]||'';if(typeof s!=='string'||s.length>2000)fail('제어 실험 노트가 너무 깁니다.');x.notes[m][k]=s;}}
    const ids=new Set();
    for(const r of x.records){
      if(!Number.isInteger(r.id)||r.id<1||ids.has(r.id)||!/^#[0-9a-f]{6}$/i.test(r.color)||!r.result||!r.result.parameters||!['pid','lqr','lmpc'].includes(r.result.method)||typeof r.result.status!=='string'||!Array.isArray(r.rows)||r.rows.length>2000)fail('제어 실험 행을 확인해 주세요.');
      ids.add(r.id);number(r.result.duration,0,1000,'실험 시간');
      let last=-1;for(const row of r.rows){for(const k of ['t','error','arm','u'])number(row[k],-1e12,1e12,k);if(row.t<last)fail('제어 실험 시간 순서가 다릅니다.');last=row.t;}
    }
    if(!Array.isArray(x.selected)||x.selected.length>3||x.selected.some(id=>!ids.has(id)))fail('제어 비교 선택을 확인해 주세요.');
    return x;
  }
  function normalize(value) {
    if(value===undefined||value===null)return empty();
    const x=data(value),out=empty();if(x.v!==1||!missions.some(m=>m.id===x.active))fail('수업 미션 버전을 확인해 주세요.');out.active=x.active;
    for(const m of missions){const n=x.missions&&x.missions[m.id];if(!n)continue;const row={};for(const k of ['predict','observe','explain']){row[k]=n[k]||'';if(typeof row[k]!=='string'||row[k].length>2000)fail('미션 글은 2,000자 이내로 적어 주세요.');}row.runs=Array.isArray(n.runs)?n.runs.slice():[];if(row.runs.length>100||row.runs.some(n=>!Number.isInteger(n)||n<1))fail('미션의 실험 번호를 확인해 주세요.');row.complete=n.complete===true;out.missions[m.id]=row;}
    out.primer=primer(x.primer);out.control=control(x.control);return out;
  }
  function metrics(samples) {
    let last=0,total=0,u2=0,hold=0,streak=0,capture=null,err=0,after=0;
    samples.forEach(s=>{const dt=Math.max(0,s.t-last);last=s.t;total+=dt;u2+=s.u*s.u*dt;const inside=Math.abs(s.error)<=5&&Math.abs(s.velocity)<=.5;
      if(inside){hold+=dt;streak+=dt;if(capture===null&&streak>=.5-1e-9)capture=s.t-streak;}else streak=0;
    });
    last=0;if(capture!==null)samples.forEach(s=>{const dt=Math.max(0,s.t-Math.max(last,capture));last=s.t;err+=Math.abs(s.error)*dt;after+=dt;});
    return {duration:total,uprightSeconds:hold,captureTime:capture,postCaptureMAE:after?err/after:null,rmsAction:total?Math.sqrt(u2/total):null};
  }
  function compare(a,b) {
    if(!a||!b||!a.snapshot||!b.snapshot)return {compatible:false,changes:['이전 형식에는 비교 조건이 저장되어 있지 않습니다.']};
    const x=a.snapshot,y=b.snapshot,changes=[];
    for(const pair of [['rewardKey','보상 규칙'],['options','학습·시험 조건'],['source','실행 환경'],['modelSignature','플랜트'],['start','시작 조건'],['policyDigest','정책'],['learningSource','정책 준비 방식']])if(JSON.stringify(x[pair[0]])!==JSON.stringify(y[pair[0]]))changes.push(pair[1]);
    return {compatible:x.source===y.source&&x.source==='sim'&&x.modelSignature===y.modelSignature&&JSON.stringify(x.start)===JSON.stringify(y.start)&&x.seconds===y.seconds,changes:changes.length?changes:['설정 변경 없음 · 같은 조건의 반복 시험']};
  }
  function digest(value){let h=2166136261;for(const c of JSON.stringify(value)){h^=c.charCodeAt(0);h=Math.imul(h,16777619);}return (h>>>0).toString(16);}
  P.Classroom={missions,empty,normalize,primer,control,data,metrics,compare,digest};
})(typeof window!=='undefined'?window:globalThis);
