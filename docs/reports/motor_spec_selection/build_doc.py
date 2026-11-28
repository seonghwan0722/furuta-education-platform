from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
D='/mnt/project-files/motor_report/motor_spec_selection/'
OLD='/mnt/project-files/motor_report/rmd_selection/figures/'
doc=Document()
for s in doc.sections: s.left_margin=s.right_margin=Cm(2.2); s.top_margin=s.bottom_margin=Cm(2.0)
def font(st,size=10.5):
    st.font.name='맑은 고딕'; st.font.size=Pt(size); st.element.rPr.rFonts.set(qn('w:eastAsia'),'맑은 고딕')
font(doc.styles['Normal'])
for n,sz in (('Heading 1',14),('Heading 2',12),('Title',18)):
    st=doc.styles[n]; font(st,sz); st.font.color.rgb=RGBColor(0x1F,0x3A,0x5F)
def P(t,bold=False,size=None,italic=False,align=None):
    p=doc.add_paragraph(); r=p.add_run(t); r.bold=bold; r.italic=italic
    if size: r.font.size=Pt(size)
    if align is not None: p.alignment=align
    p.paragraph_format.space_after=Pt(4); p.paragraph_format.line_spacing=1.35; return p
def B(items):
    for t in items: doc.add_paragraph(t,style='List Bullet')
def shade(c,h):
    tcPr=c._tc.get_or_add_tcPr(); sh=OxmlElement('w:shd'); sh.set(qn('w:val'),'clear'); sh.set(qn('w:color'),'auto'); sh.set(qn('w:fill'),h); tcPr.append(sh)
def T(cap,hdr,rows,widths=None,note=None,hl=None):
    P(cap,bold=True,size=10)
    t=doc.add_table(rows=1,cols=len(hdr)); t.style='Table Grid'
    for i,h in enumerate(hdr):
        c=t.rows[0].cells[i]; c.text=''; r=c.paragraphs[0].add_run(h); r.bold=True; r.font.size=Pt(9); shade(c,'DCE6F0')
    for ri,row in enumerate(rows):
        cs=t.add_row().cells
        for i,v in enumerate(row):
            cs[i].text=''; r=cs[i].paragraphs[0].add_run(str(v)); r.font.size=Pt(9)
            if hl is not None and ri==hl: shade(cs[i],'FFF1E6'); r.bold=True
            if str(v).startswith('미측정') or str(v).startswith('확인 필요'): r.font.color.rgb=RGBColor(0x99,0x33,0x33)
    if widths:
        for row in t.rows:
            for i,w in enumerate(widths): row.cells[i].width=Cm(w)
    if note: P(note,size=8.5,italic=True)
    doc.add_paragraph()
def F(path,cap,w=16):
    doc.add_picture(path,width=Cm(w)); doc.paragraphs[-1].alignment=WD_ALIGN_PARAGRAPH.CENTER
    P(cap,size=9,align=WD_ALIGN_PARAGRAPH.CENTER)

doc.add_paragraph('RMD-X6 실험 기반 모터 요구 사양 산정과 가성비 모터 선정',style='Title')
P('Furuta 회전 역진자 강화학습 교구 · 암 구동 모터 · 작성 2026-11-28 · 근거 자료는 8장',size=9)

doc.add_heading('1. 요약',level=1)
P('연구실이 보유한 고성능 모터 MYACTUATOR RMD-X6-P20-60-E로 시스템을 먼저 실물 검증하고, 그 실험에서 얻은 동작(암 속도·가속도, 진자 운동)과 측정·식별값을 이용해 교구에 실제로 필요한 모터 토크·속도 사양을 산정한 뒤, 이 사양을 만족하는 모터 중 비용 대비 성능이 가장 좋은 모터를 최종 선정하였다. 이는 2차 설계보고서의 "구동 모터 선정 4단계"(STEP 1 기준 시뮬레이션 → STEP 2 연구실 모터 실물 확인 → STEP 3 요구 토크·회전수 탐색 → STEP 4 최저가 모터 선정)를 따른 것이다.')
P('핵심 발견은 RMD-X6가 실물 시험에서 낸 토크(최대 3.15 N·m, RMS 0.6~1.6 N·m)의 대부분이 RMD 자신의 감속기 마찰과 반사 관성을 이기는 데 쓰였다는 점이다. 같은 동작을 만드는 데 암·진자 자체가 요구하는 토크는 최대 0.13 N·m, RMS 0.017 N·m에 불과했다. 여기에 안전율 1.5를 적용해 요구 사양을 피크 0.20 N·m 이상, 연속 0.03 N·m 이상, 암 속도 20 rad/s(191 rpm) 이상으로 정하였다.')
P('후보 9종을 구동계 전체 비용(모터 + 필요한 드라이버·엔코더·MCU)으로 비교한 결과, MYACTUATOR RMD-L-5010-35T(직결형, 드라이버·엔코더·CAN 내장, 약 13.3만 원)를 최종 선정하였다. 요구 피크 대비 3.3배, 연속 대비 8.7배, 속도 대비 3.1배의 여유가 있고, 비용은 RMD-X6의 약 1/8이며, RMD-X6와 같은 제조사의 CAN 모터라 현재 Pi 5 + CAN 구동 경로를 그대로 쓸 가능성이 높다.',bold=True)

doc.add_heading('2. 접근 방법: 모터 선정 4단계',level=1)
T('표 1. 모터 선정 4단계와 이번 작업의 대응',['단계','계획(2차 보고서)','이번 수행 내용'],
 [['STEP 1 기준 시뮬레이션','연구실 고성능 모터의 한계를 모델에 넣고 학습','rev11 MuJoCo + RMD 반사 관성으로 토크·속도 요구 확인(motor_sizing_rev11), PPO·SAC·LQR·PID·LMPC 설계'],
  ['STEP 2 연구실 모터 실물 확인','같은 제어기를 연구실 모터 시작품에 적용','Pi 5 + RMD-X6 실물 시험: 전류 응답, 정지마찰, 5개 제어기 스윙업·직립 통과, 식별 플랜트 hw1123'],
  ['STEP 3 요구 토크·회전수 탐색','토크·전류 한계를 낮추며 최솟값 탐색','RMD 토크를 감속기 몫과 부하 몫으로 분리(역동역학)하여 직결 구동 기준 최소 토크·속도 산정 (4장)'],
  ['STEP 4 최저가 모터 선정','요구 × 1.5 이상 중 가장 싼 모터','후보 9종 구동계 비용 비교 → RMD-L-5010-35T 선정 (5~6장)']],widths=[3.4,5.2,8.4])
P('STEP 3을 계획대로 "RMD 전류 상한을 단계적으로 낮추는" 방식으로 하지 않은 이유: RMD-X6는 정지마찰만 약 0.63~0.79 N·m이어서 전류를 낮추면 감속기 마찰에서 먼저 막힌다. 이렇게 얻은 최솟값은 RMD 감속기의 특성이지 교구가 필요로 하는 토크가 아니다. 그래서 실물로 검증된 동작을 그대로 두고, 그 동작에 필요한 토크를 감속기 몫과 부하 몫으로 나누어 계산했다.')

doc.add_heading('3. STEP 1~2: RMD-X6로 얻은 실험값',level=1)
T('표 2. 연구실 RMD-X6 실험·식별값',['항목','값','출처'],
 [['전류 추종 (지령 0.1 / 0.3 / 0.5 A)','RMD 보고 0.095 / 0.294 / 0.495 A (오차 5 mA 이내)','pi_current_03~06'],
  ['정지마찰 (출발 전류)','약 0.3 A ≈ 0.63 N·m','pi_current_03~06'],
  ['식별 플랜트 hw1123 (11/23)','암 등가 관성 0.0252 kg·m², 쿨롱 0.785 N·m, 점성 0.186 N·m·s','README_인수인계, 최종발표 정리'],
  ['  └ 그중 암·진자 자체 관성','2.36×10⁻⁴ kg·m² (등가 관성의 약 1%)','MuJoCo rev11 J_BODY'],
  ['운용 전류 상한','1.5 A × 2.1 N·m/A = 3.15 N·m (스윙업 중 포화)','전 제어기 실물 시험'],
  ['실물 판정 통과 제어기','PID 2/2, LQR 1/1, LMPC 1/2, PPO run9 통과, SAC sac24 3/3·sac22 3/3','report_final, README_인수인계'],
  ['스윙업 중 암 최고 속도','PPO 약 9.3~9.5, SAC 11.5, LMPC 약 13 rad/s (일부 그래프 판독)','실물 로그 그림'],
  ['스윙업 중 실제 상전류 피크, 모터 온도, 회생 버스 전압','미측정','–']],widths=[4.6,7.6,4.8])
F(OLD+'fig3_current.png','그림 0. RMD-X6 전류 지령 대비 응답 (0.3 A까지 정지마찰로 정지)',w=10.5)

doc.add_heading('4. STEP 3: 교구에 필요한 토크·속도 산정',level=1)
doc.add_heading('4.1 방법',level=2)
P('실물 통과 정책 3개(SAC sac24 ck0100, SAC sac22 ck0150, PPO run9 ck0380)를 실물 로그로 맞춘 식별 플랜트(hw1123, 그리고 비교용 nom10)에서 Pi와 같은 관측·지연·0.01 A 양자화 조건으로 다시 실행했다. 이 해석 모델은 MATLAB 평가와 88/88칸이 일치하고, 정책별 실물 결과와도 맞는 모델이다. 매달림 근처 출발 11개, 20 s씩 실행하여 매 10 ms의 상태와 가속도를 얻었다.')
P('암 운동방정식을 세 부분으로 나누었다 (θ: 진자, 0 = 직립; φ: 암).')
P('τ_RMD = (α − J_body)·φ̈  +  [η·φ̇ + F_c·sign(φ̇)]  +  τ_load', bold=True, align=WD_ALIGN_PARAGRAPH.CENTER)
P('τ_load = (J_body + β sin²θ)·φ̈ + γ cosθ·θ̈ + 2β sinθ cosθ·φ̇θ̇ − γ sinθ·θ̇²', align=WD_ALIGN_PARAGRAPH.CENTER)
P('첫 항은 감속기 반사 관성(α = 0.0252, J_body = 2.36×10⁻⁴ kg·m²), 둘째 항은 감속기 마찰(η = 0.186, F_c = 0.785), 셋째 항은 암·진자가 요구하는 토크다. 진자 운동은 암 운동에만 의존하므로, 직결 모터가 τ_direct = τ_load + J_rotor·φ̈ + (베어링 마찰 0.012 N·m 쿨롱 + 1×10⁻⁴ 점성)를 내면 RMD 실험과 똑같은 동작이 나온다. 이 τ_direct가 교구에 필요한 토크다.')
doc.add_heading('4.2 결과',level=2)
T('표 3. RMD 토크 분해와 직결 구동 필요 토크 (통과 실행 기준, J_rotor = 2×10⁻⁵ kg·m²)',
 ['플랜트·정책','통과','RMD 토크 피크 / RMS','감속기 마찰 RMS','감속기 관성 RMS','직결 필요 피크 / RMS','암 최고속도','기계 출력 피크'],
 [['hw1123 · SAC sac24','11/11','3.11 / 1.17','1.09','0.44','0.082 / 0.015','8.0 rad/s','0.45 W'],
  ['hw1123 · SAC sac22','11/11','3.11 / 1.65','1.60','0.41','0.097 / 0.015','7.9 rad/s','0.59 W'],
  ['hw1123 · PPO run9','9/11','3.15 / 1.13','1.04','0.50','0.100 / 0.016','10.0 rad/s','0.68 W'],
  ['nom10 · SAC sac24','11/11','3.11 / 0.63','0.52','0.38','0.108 / 0.015','11.0 rad/s','0.84 W'],
  ['nom10 · SAC sac22','8/11','3.11 / 0.69','0.58','0.39','0.122 / 0.014','11.2 rad/s','1.03 W'],
  ['nom10 · PPO run9','8/11','3.15 / 0.59','0.50','0.34','0.096 / 0.014','13.2 rad/s','0.99 W']],
 widths=[3.2,1.3,2.4,1.8,1.8,2.4,1.8,1.6],note='토크 단위 N·m. 성분 RMS는 서로 상관이 있어 합이 전체 RMS와 같지 않다.')
F(D+'figures/figA_torque_timeseries.png','그림 1. 같은 스윙업 동작에서 RMD-X6가 낸 토크(파랑)와 실제 필요한 부하 토크(주황)')
F(D+'figures/figB_decomposition.png','그림 2. RMD-X6 토크 성분별 RMS. 암·진자 부하 몫은 감속기 몫의 약 1/100이다.')
T('표 4. 직결 모터 회전자 관성에 따른 필요 피크 토크 (6개 조건 중 최대)',['회전자 관성 J_rotor [kg·m²]','0','6.1×10⁻⁶','2×10⁻⁵','5×10⁻⁵','1×10⁻⁴','3×10⁻⁴'],
 [['필요 피크 토크 [N·m]','0.121','0.121','0.122','0.123','0.125','0.134'],['필요 RMS 토크 [N·m]','0.016','0.016','0.016','0.017','0.017','0.019']],
 note='회전자 관성이 1×10⁻⁴ kg·m² 이하면 결과가 거의 바뀌지 않는다.')
doc.add_heading('4.3 요구 사양',level=2)
T('표 5. 교구용 암 구동 모터 요구 사양',['항목','산정값','안전율 적용 요구 사양','근거'],
 [['피크 토크','0.125 N·m (최대, J_rotor ≤ 1×10⁻⁴)','≥ 0.20 N·m','× 1.5 (2차 보고서 STEP 4 기준)'],
  ['연속(RMS) 토크','0.017 N·m','≥ 0.03 N·m','× 1.5 후 올림'],
  ['암 최고 속도','실물 약 13 rad/s, 인터록 15 rad/s','≥ 20 rad/s (191 rpm)','인터록 15 × 1.3'],
  ['기계 출력','≤ 1.03 W','수 W급이면 충분','표 3'],
  ['회전자 관성','–','≤ 1×10⁻⁴ kg·m² 권장','표 4'],
  ['엔코더','실물은 RMD 0.01° 각도 사용','14 bit 이상 (0.022°)','관측 양자화'],
  ['인터페이스','현재 Pi 5 + CAN HAT','CAN 드라이버 내장 우선','소프트웨어 재사용, 드라이버·MCU 비용 절감']],widths=[2.6,4.6,3.6,6.2])
P('참고: 11/06 직결 가정 시뮬레이션의 설계값(피크 0.08 N·m, 연속 0.03 N·m)과 같은 범위다. 다만 당시 요구 속도 40 rad/s는 속도 제한 없는 제어기 기준이었고, RMD 실험에서 15 rad/s 인터록으로도 모든 제어기가 통과했으므로 20 rad/s로 낮췄다.',size=9.5,italic=True)

doc.add_heading('5. STEP 4: 후보 모터 비교',level=1)
P('후보는 프로젝트에서 이미 조사한 모터(11/06~11/09 조사)와 RMD-X6와 같은 제조사의 직결형 CAN 모터를 포함했다. 짐벌형 모터는 FOC 드라이버(₩35,000)·MCU(₩12,000)·필요 시 엔코더(₩18,000)를 더한 구동계 비용으로 비교했다(과제계획서 예산 단가). 환율은 $1 = ₩1,400으로 가정했다.')
T('표 6. 후보 모터 비교',['모델','형식','정격 / 피크 토크 [N·m]','속도','엔코더·드라이버','구동계 비용','판정'],
 [['RMD-X6-P20-60-E (기준)','감속 19.6:1, CAN 일체','20 / 50','153 rpm','17 bit, 내장','₩103.9만 ($741.84)','과사양, 속도 여유 작음'],
  ['RMD-L-5010-35T','직결, CAN 일체','0.26 / 0.65','600 rpm (최대 1,015)','14 bit, 내장','₩13.3만 ($95)','선정'],
  ['GM5208-12 + AS5048A','짐벌, 별도 FOC','0.18~0.25 (1 A)','24 V 필요','14 bit, 별도','₩13.4만','경계(하한 미달)'],
  ['GM3506 + AS5048A','짐벌, 별도 FOC','0.06~0.1','–','14 bit, 별도','₩10.6만','미달'],
  ['GM2804','짐벌, 별도 FOC','0.025~0.034','–','별도','₩9.0만','미달'],
  ['CubeMars GL40 KV70','짐벌, 별도 FOC','0.25 / 0.5','16 V 정격','미포함','₩16.7만','충족'],
  ['CubeMars GL35 KV100','짐벌, 별도 FOC','0.15 / 0.46','815 rpm','포함(방식 미상)','₩19.7만','충족'],
  ['LK MHF5005','직결, CAN/RS485 일체','0.12 / 0.4','1,700 rpm','19 bit, 내장','₩17.3만','충족'],
  ['Steadywin OT4307','직결, CAN 일체','0.15 / 0.45','2,700 rpm','16 bit, 내장','₩21.3만','충족']],
 widths=[3.3,2.6,2.2,2.2,2.4,2.4,1.9],hl=1,
 note='가격은 판매 페이지 표시가(RMD 두 모델은 11/28 RobotShop 확인, 나머지는 11/06~09 조사값으로 재확인 필요). 배송·관세 제외.')
F(D+'figures/figC_cost_torque.png','그림 3. 후보 모터의 구동계 비용 대비 피크 토크. 점선 위가 요구 사양 충족 영역이다.')

doc.add_heading('6. 최종 선정: MYACTUATOR RMD-L-5010-35T',level=1)
T('표 7. 선정 모터 여유율',['항목','요구 사양','RMD-L-5010-35T','여유'],
 [['피크 토크','≥ 0.20 N·m','0.65 N·m (순간 최대)','3.3배 (필요 0.125 대비 5.2배)'],
  ['연속 토크','≥ 0.03 N·m','0.26 N·m (정격)','8.7배'],
  ['속도','≥ 20 rad/s','600 rpm = 62.8 rad/s (정격)','3.1배'],
  ['회전자 관성','≤ 1×10⁻⁴ kg·m²','2.02×10⁻⁵ kg·m² (202 g·cm²)','충족'],
  ['엔코더','≥ 14 bit','14 bit 자기식 (판매처별 16~18 bit 표기 상이)','충족'],
  ['인터페이스','CAN 내장 우선','CAN 1 Mbps, 드라이버 내장','충족'],
  ['구동계 비용','최저','₩13.3만 (RMD-X6의 약 1/8)','후보 중 최저(충족 모델 기준)']],widths=[2.6,3.4,5.6,5.4])
P('선정 근거',bold=True)
B(['비용: 요구를 충족하는 후보 중 구동계 비용이 가장 낮다. 같은 가격대의 GM5208-12는 토크가 요구 하한에 걸리고 별도 FOC 드라이버·MCU·펌웨어가 필요하다.',
   '통합성: 드라이버·엔코더·CAN이 내장되어, 이미 검증한 Pi 5 + CAN HAT 구조를 그대로 쓴다. 별도 MCU와 FOC 펌웨어가 필요 없다.',
   '소프트웨어 재사용: RMD-X6와 같은 MYACTUATOR CAN 제품군이라 0x92 각도 조회, 0xA1 전류 지령 등 기존 Pi 프레임 코드를 재사용할 가능성이 높다(프로토콜 버전 확인 필요).',
   '동특성: 감속기가 없어 백래시(10′)와 큰 정지마찰(0.63~0.79 N·m)이 사라진다. RMD-X6에서 SAC가 처음 실패한 원인(정지마찰 민감)도 줄어든다.'])
P('주의할 점과 다음 단계',bold=True)
B(['전원: 입력 8~24 V라 현재 48 V 전원(LRS-350-48)은 쓸 수 없다. 24 V 전원으로 바꿔야 한다.',
   '제어기·정책 재조정: 암 등가 관성이 0.0252 → 약 2.6×10⁻⁴ kg·m²로 약 1/100이 된다. LQR·PID 게인과 PPO·SAC 정책은 새 플랜트로 다시 설계·학습해야 한다(RMD-X6 정책을 그대로 쓰면 안 된다).',
   '토크 분해능: 전류 1 LSB(0.01 A)에 해당하는 토크는 RMD-L의 토크 상수에 따라 달라진다. 토크 상수는 판매 페이지에 없어 확인이 필요하다.',
   '중공축: 한 판매처만 Ø12.7 mm 중앙 구멍을 표기한다. 슬립링·배선 통과가 필요하면 구매 전 확인한다.',
   '실물 검증: 구매 후 같은 판정 기준(20 s 안에 도립, ±5°·±0.5 rad/s 5 s 유지)으로 STEP 2를 다시 수행해 선정을 확정한다.'])
P('차선: 속도·토크 여유와 중공축이 더 중요하면 LK MHF5005(₩17.3만, 19 bit) 또는 CubeMars GL40 KV70(₩16.7만, 별도 드라이버)을 고려할 수 있다.')

doc.add_heading('7. 결론',level=1)
P('연구실 RMD-X6로 제어 시스템 전체를 실물 검증하고, 그 동작을 감속기 몫과 부하 몫으로 분리해 교구가 실제로 필요로 하는 모터 사양(피크 0.20 N·m, 연속 0.03 N·m, 20 rad/s)을 산정했다. RMD-X6의 토크는 사양 대비 100배 이상 과하고 대부분 자기 감속기에 쓰이므로, 교구에는 직결형 소형 CAN 모터가 맞다. 이 사양을 만족하는 후보 중 비용이 가장 낮은 RMD-L-5010-35T(₩13.3만)를 최종 선정하였다.')

doc.add_heading('8. 데이터 출처 · 가정 · 미측정 항목',level=1)
T('표 8. 데이터 출처',['자료','사용한 값'],
 [['handoff_pi_motor_20261119.md','전류 시험, 정지마찰, Kt 2.1 N·m/A'],
  ['handoff_python_20261124.zip (xcheck.py, matlab_export, policies)','식별 플랜트 hw1123·nom10, 실물 통과 정책 3개 재실행, 운동방정식 계수(β, γ, J_body)'],
  ['motor_report/motor_spec_selection/invdyn.py, invdyn.json','표 3·4 역동역학 계산 코드와 결과(재현 가능)'],
  ['report_final, final_presentation, README_인수인계.md','실물 판정 결과, 암 최고 속도'],
  ['report2/src_v3/content.py (2차 보고서 표 20)','모터 선정 4단계, 안전율 1.5'],
  ['motor_report/중공축_엔코더_모터_선정_보고서.docx, 프로젝트 메모(11/06~09)','OT4307·MHF5005·GL35·GL40·GM 계열 사양·가격'],
  ['plan/캡스톤디자인_과제계획서_입력용.md','FOC 드라이버 ₩35,000, AS5048A ₩18,000, MCU ₩12,000'],
  ['RobotShop RMD-L-5010-35T · RMD-X6-P20 페이지, rcdrone.top, OpenELAB (11/28 확인)','RMD-L 사양·$95, RMD-X6 $741.84(EtherCAT 표기 묶음) / €427.95']],widths=[6.5,10.5])
P('가정',bold=True)
B(['필요 토크는 실물 통과 정책을 식별 플랜트에서 다시 실행한 궤적으로 계산했다. 실물 로그(.mat)에서 직접 계산한 것은 아니다.',
   '직결 모터의 베어링 마찰은 쿨롱 0.012 N·m(rev11 모델 가정값) + 점성 1×10⁻⁴ N·m·s로 두었다. 코깅 토크는 넣지 않았다.',
   '같은 궤적을 직결 모터로 낸다는 계산이다. 실제로는 새 플랜트에 맞춰 제어기를 다시 설계하므로 궤적이 달라질 수 있으나, 같은 판정을 만족하는 궤적이 존재함을 보여 준다.',
   '환율 $1 = ₩1,400, €1 = ₩1,500. 배송비·관세 제외.'])
P('미측정·확인 필요',bold=True)
B(['RMD-L-5010-35T의 토크 상수, 프로토콜 버전(V3/V4) 호환, 중공축 여부','11/06~09 조사 가격의 현재 시세','RMD-X6 실물 스윙업 중 실제 상전류 피크·온도·회생 전압'])
doc.save(D+'모터_요구사양_산정_및_가성비_모터_선정.docx'); print('saved')
