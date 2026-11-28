from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
D='/mnt/project-files/motor_report/rmd_selection/'
doc=Document()
for s in doc.sections: s.left_margin=s.right_margin=Cm(2.2); s.top_margin=s.bottom_margin=Cm(2.0)
def font(st,size=10.5):
    st.font.name='맑은 고딕'; st.font.size=Pt(size)
    st.element.rPr.rFonts.set(qn('w:eastAsia'),'맑은 고딕')
font(doc.styles['Normal'])
for n,sz in (('Heading 1',14),('Heading 2',12),('Title',18)):
    st=doc.styles[n]; font(st,sz); st.font.color.rgb=RGBColor(0x1F,0x3A,0x5F)
def P(t,bold=False,size=None,italic=False,align=None):
    p=doc.add_paragraph(); r=p.add_run(t); r.bold=bold; r.italic=italic
    if size: r.font.size=Pt(size)
    if align: p.alignment=align
    p.paragraph_format.space_after=Pt(4); p.paragraph_format.line_spacing=1.35
    return p
def shade(c,hexc):
    tcPr=c._tc.get_or_add_tcPr(); sh=OxmlElement('w:shd'); sh.set(qn('w:val'),'clear'); sh.set(qn('w:color'),'auto'); sh.set(qn('w:fill'),hexc); tcPr.append(sh)
def T(cap,hdr,rows,widths=None,note=None):
    P(cap,bold=True,size=10)
    t=doc.add_table(rows=1,cols=len(hdr)); t.style='Table Grid'
    for i,h in enumerate(hdr):
        c=t.rows[0].cells[i]; c.text=''; r=c.paragraphs[0].add_run(h); r.bold=True; r.font.size=Pt(9); shade(c,'DCE6F0')
    for row in rows:
        cs=t.add_row().cells
        for i,v in enumerate(row):
            cs[i].text=''; r=cs[i].paragraphs[0].add_run(str(v)); r.font.size=Pt(9)
            if str(v).startswith('미측정'): r.font.color.rgb=RGBColor(0x99,0x33,0x33)
    if widths:
        for row in t.rows:
            for i,w in enumerate(widths): row.cells[i].width=Cm(w)
    if note: P(note,size=8.5,italic=True)
    doc.add_paragraph()
def F(path,cap,w=16):
    doc.add_picture(D+'figures/'+path,width=Cm(w)); doc.paragraphs[-1].alignment=WD_ALIGN_PARAGRAPH.CENTER
    P(cap,size=9,align=WD_ALIGN_PARAGRAPH.CENTER)

doc.add_paragraph('암 구동 모터 선정 근거',style='Title')
P('연구실 보유 MYACTUATOR RMD-X6-P20-60-E 실험값 기반 최종 선정',bold=True,size=12)
P('Furuta 회전 역진자 강화학습 교구 · 작성 2026-11-27 · 근거 자료는 7장에 정리',size=9)

doc.add_heading('1. 요약',level=1)
P('암 구동 모터는 연구실이 보유한 MYACTUATOR RMD-X6-P20-60-E(48 V, 감속비 19.612, 드라이버·엔코더·CAN 내장)로 최종 선정하였다. '
  '선정은 두 단계로 진행했다. 먼저 rev11 MuJoCo 모델로 스윙업과 직립 유지에 필요한 토크·속도를 산정했고, 다음으로 연구실 모터를 Raspberry Pi 5와 CAN으로 직접 구동하여 '
  '전류 응답, 정지마찰, 암 최고 속도, 제어기별 최대 지령 전류를 측정했다. 측정값을 요구값 및 제조사 사양과 비교해 여유율을 확인한 뒤 최종 결정했다.')
P('핵심 수치는 다음과 같다. 실물 운용 상한 1.5 A(출력축 3.15 N·m)에서 PID·LQR·LMPC·PPO·SAC 다섯 제어기가 모두 스윙업·직립 판정을 통과했고, 이 값은 정격 토크 20 N·m의 16%, 피크 토크의 6% 수준이다. '
  '측정된 정지마찰(0.63~0.79 N·m)보다 4배 이상 크고, 시뮬레이션의 약 2 s 스윙업 요구 토크(1.0 N·m)보다 3배 이상 크다. '
  '반면 속도 여유는 작다. 실물 스윙업 중 암 최고 속도는 약 13 rad/s로 정격 속도(16.0 rad/s)의 81%여서, 암 속도 인터록 15 rad/s를 두고 운용한다.')
P('즉, 이 모터는 토크 측면에서 충분한 여유를 갖고, 속도 측면에서는 정격 범위 안에 있으나 여유가 작으므로 소프트웨어 속도 제한과 함께 사용하는 조건으로 선정하였다.',bold=True)

doc.add_heading('2. 선정 경과',level=1)
P('초기에는 암을 모터에 직결하는 소형 짐벌 BLDC(GM2804, GM5208, CubeMars GL35 등)를 후보로 검토했다. 직결 구동 가정에서 rev11 모델의 요구 토크는 피크 약 0.08 N·m(안전계수 1.5 포함), 연속 약 0.03 N·m로 작았다. '
  '그러나 이 후보들은 별도 드라이버(SimpleFOC)·별도 엔코더·MCU(Teensy)가 필요했고, 엔코더 장착과 배선이 복잡했다.')
P('2026-11-17 연구실이 보유한 RMD-X6-P20-60-E를 사용하는 안으로 바꾸었다. 이 모터는 FOC 드라이버와 출력축 17비트 엔코더를 내장하고 CAN으로 전류 지령을 받으므로, Raspberry Pi 5와 CAN HAT만으로 구동 경로가 완성된다. '
  '다만 감속기의 반사 관성(약 0.025 kg·m²)과 정지마찰 때문에 직결 구동보다 큰 토크가 필요하고, 감속기 때문에 최고 속도가 낮아진다. 따라서 "토크와 속도가 실제로 충분한가"를 시뮬레이션과 실물 실험으로 확인하는 것이 선정의 핵심이었다.')

doc.add_heading('3. 시뮬레이션 요구값 (rev11 MuJoCo + RMD 반사 관성)',level=1)
P('rev11 ㄱ자 일체형 암-진자 모델(진자 31.9 g, l = 84.5 mm)에 RMD 반사 관성(armature 0.025 kg·m²)을 넣고, 토크 상한을 바꿔 가며 에너지 스윙업 + LQR 포착이 성립하는 조건을 찾았다. '
  '마찰은 모델 기본값(1배)과 8배 두 경우를 비교했다.')
T('표 1. 토크 상한별 스윙업 성립 여부 (motor_sizing_rev11/rmd_ct.json)',
  ['마찰','토크 상한 [N·m]','스윙업','직립 도달 [s]','암 최고속도 [rad/s]','최대 기계 출력 [W]','직립 유지 피크 [N·m]'],
  [['1배','0.5','성립','4.77','8.0','3.9','0.50'],['1배','1.0','성립','2.29','9.0','9.0','0.49'],['1배','2.0','성립','0.93','10.4','19.7','0.43'],['1배','4.0','성립','0.48','17.6','56.3','0.58'],
   ['8배','0.5','불성립','–','–','–','–'],['8배','1.0','성립','5.37','15.9','15.8','0.86'],['8배','2.0','성립','2.16','16.6','33.0','0.98'],['8배','4.0','성립','0.51','18.0','65.4','0.87']],
  note='해석: 스윙업 최소 0.5~1.0 N·m, 약 2 s 스윙업에는 1~2 N·m가 필요하다. 토크를 키우면 도달 시간은 줄지만 암 속도가 16~18 rad/s까지 올라가 감속기 정격 속도에 가까워진다.')

doc.add_heading('4. 연구실 보유 RMD 모터 실험',level=1)
P('시험 구성: Raspberry Pi 5 → SEENGREAT CAN HAT(MCP2515, can0, 1 Mbps) → RMD-X6(요청 0x141 / 응답 0x241, 0xA1 전류 지령 0.01 A 단위), 전원 MEAN WELL LRS-350-48(48 V, 7.3 A), 진자 엔코더 AS5600. '
  '제어 주기 10 ms(각도 조회 5 ms + 전류 지령 5 ms). 실험은 (1) 전류 지령 단독 응답 시험(11/18~19)과 (2) 제어기별 스윙업·직립 실물 시험(11/20~24)으로 나뉜다.')
T('표 2. 실물 실험 측정값',
  ['항목','측정값','시험·로그','비고'],
  [['전류 추종 (지령 0.1 / 0.3 / 0.5 A)','RMD 보고 평균 0.095 / 0.294 / 0.495 A','pi_current_03, 04, 06','오차 5 mA 이내'],
   ['정지마찰 (출발 전류)','약 0.3 A ≈ 0.63 N·m','pi_current_03~06','0.3 A에서 정지, 0.5 A에서 0.05 s 만에 출발'],
   ['0.5 A 정속 회전 속도','약 2.35 rad/s (22 rpm)','pi_current_06','출발 가속도 약 7.8 rad/s²'],
   ['등가 관성 (암)','약 0.05 kg·m²(전류 시험 추정) / 0.0252 kg·m²(11/23 식별)','pi_current_06, hw1123','11/23 식별값이 최신'],
   ['쿨롱·점성 마찰 (식별)','0.785 N·m / 0.186 N·m·s','hw1123 (11/23)','로그 재현용 식별값'],
   ['운용 전류 상한 (스윙업 시 포화)','1.5 A 지령 = 3.15 N·m','전 제어기 실물 시험','스윙업 구간 ±1.5 A 도달 (그림 지령 기록)'],
   ['직립 유지 구간 최대 지령','0.87 A ≈ 1.83 N·m, 포화 0%','ppo_rev11_tol2_13','LMPC는 ±1.5 A 포화 19%(채터링)'],
   ['스윙업 중 암 최고 속도','PPO 약 9.3~9.5 · SAC 11.5 · LMPC 약 13 rad/s','tol2_13, tol2b_19, tol2_15, tol2_14','PPO·LMPC는 로그 그래프 판독값'],
   ['CAN 응답 지연','약 0.13 ms (요청-응답 1:1)','candump','5 ms 슬롯 안'],
   ['스윙업 중 실제 상전류(RMD 보고)','미측정','–','로그는 지령 전류 위주, 응답 전류 피크 미집계'],
   ['모터 온도 · 버스 전압','미측정','–','고속 반전 제동 시 회생 과전압으로 응답 중단 1회 관찰(크기 미측정)']],
  widths=[4.2,4.8,3.4,4.6])
F('fig3_current.png','그림 3. 전류 지령 대비 RMD 응답. 0.3 A까지는 정지마찰로 회전하지 않고, 0.5 A에서 출발했다.',w=11.5)

doc.add_heading('5. 요구값 · 실험값 · 모터 사양 비교',level=1)
T('표 3. 여유율 정리',
  ['구분','비교 대상','값','기준 (사양 또는 운용 상한)','여유'],
  [['토크','실물 운용 상한 (1.5 A)','3.15 N·m','정격 20 N·m / 피크 50 N·m','정격의 16% (6.3배), 피크의 6% (15.9배)'],
   ['토크','시뮬 약 2 s 스윙업 요구','1.0 N·m','운용 상한 3.15 N·m','3.2배'],
   ['토크','측정 정지마찰 · 식별 쿨롱마찰','0.63 · 0.79 N·m','운용 상한 3.15 N·m','4.0~5.0배'],
   ['토크','직립 유지 최대 지령 (PPO)','1.83 N·m','정격 20 N·m','정격의 9%'],
   ['전류','운용 상한','1.5 A','정격 9.5 A / 피크 29.1 A','정격의 16%, 피크의 5%'],
   ['속도','실물 스윙업 암 최고 (LMPC)','약 13 rad/s','정격 16.0 rad/s (153 rpm) / 무부하 18.4 rad/s','정격의 81% (1.23배), 무부하의 71%'],
   ['속도','암 속도 인터록','15 rad/s','정격 16.0 rad/s','정격의 94%'],
   ['출력','토크 상한 × 최고 속도 (보수적 상한)','약 41 W','정격 출력 320 W / 전원 350 W','정격의 13%'],
   ['분해능','전류 지령 1 LSB','0.01 A = 0.021 N·m','정지마찰 0.63 N·m','정지마찰의 1/30']],
  widths=[1.6,4.2,2.6,4.4,4.2],
  note='출력 41 W는 토크 상한과 최고 속도를 곱한 보수적 상한으로, 실제 동시 발생 여부는 미측정이다.')
F('fig1_torque.png','그림 1. 토크 비교 (로그 눈금). 실물 운용 상한 3.15 N·m는 시뮬레이션 요구값과 정지마찰을 넘고, 정격 토크보다 한참 아래에 있다.')
F('fig2_speed.png','그림 2. 암 각속도 비교. 실물 최고 속도 약 13 rad/s는 정격 16.0 rad/s 아래지만 여유가 작아 인터록 15 rad/s를 둔다.')
F('fig4_torque_speed.png','그림 4. 토크–속도 평면. 실물 운용 영역(파란 사각형)은 정격 영역 안 아래쪽에 있다. 마찰 8배·고토크 시뮬레이션 사례는 정격 속도를 넘으므로 토크 상한과 속도 인터록으로 피한다.')

doc.add_heading('6. 최종 선정과 운용 조건',level=1)
P('결론: 연구실 보유 RMD-X6-P20-60-E를 암 구동 모터로 최종 선정한다.',bold=True)
for t in ['토크: 실물 운용 상한 3.15 N·m로 다섯 제어기 모두 스윙업·직립을 통과했고, 이는 정격의 16%다. 정지마찰(≥0.63 N·m)을 넘는 데 필요한 전류(0.3~0.5 A)도 정격 전류의 5% 수준이다.',
          '속도: 실물 최고 약 13 rad/s로 정격 16.0 rad/s 안에 있다. 여유가 작으므로 인터록 15 rad/s를 낮추지 않고 유지하고, 학습 보상에 암 속도 벌점을 둔다.',
          '구성: 드라이버·엔코더·CAN 내장으로 Pi 5 + CAN HAT만으로 구동되며, 별도 MCU·모터 드라이버·암 엔코더가 필요 없다. 연구실 보유품이라 추가 구매가 없다.',
          '통신·제어: CAN 1 Mbps에서 요청-응답이 0.13 ms로 10 ms 제어 주기에 충분하고, 전류 추종 오차가 5 mA 이내다.']:
    doc.add_paragraph(t,style='List Bullet')
P('운용 조건과 남은 위험',bold=True)
for t in ['전류 지령 ±1.5 A 제한, 암 15 · 진자 25 rad/s 인터록, 구동 20 s 제한을 유지한다.',
          '고속 반전 제동 시 회생 과전압으로 RMD 응답이 끊긴 사례가 있어 스윙업 중 제동 전류를 차단한다. 버스 전압 실측은 남은 과제다.',
          '정지마찰(0.63~0.79 N·m)과 반사 관성(약 0.025 kg·m²)은 직결 구동보다 불리하므로 제어기·정책 학습에 반영해야 한다(SAC 초기 실패 원인 중 하나).',
          '백래시 10′(일부 판매처 15′ 이하 표기)는 직립 유지 정밀도에 영향을 줄 수 있다.']:
    doc.add_paragraph(t,style='List Bullet')

doc.add_heading('7. 데이터 출처 · 가정 · 미측정 항목',level=1)
T('표 4. 데이터 출처',['자료','사용한 값'],
  [['handoff_pi_motor_20261119.md','전류 시험 pi_current_01~06, 정지마찰 0.3 A, 정속 2.35 rad/s, 가속도 7.8 rad/s², CAN 0.13 ms, Kt 2.1 N·m/A'],
   ['report_final/실험정리_및_보고서내용.md, final_presentation/최종발표_전체정리.md','제어기별 실물 결과, 최대 지령 0.87 A, LMPC 포화 19%, SAC 암 11.5 rad/s, 식별 플랜트 hw1123(관성 0.0252, 쿨롱 0.785, 점성 0.186)'],
   ['ppo_rev11_tol2_13_detail.png, ppo_rev11b_tol2b_19_detail.png, lmpc_rev11_tol2_14_detail.png','스윙업 중 암 최고 속도(그래프 판독: 약 9.5, 9.3, 13 rad/s), 스윙업 구간 ±1.5 A 지령'],
   ['README_인수인계.md, HARDWARE_TEST_PID_LQR.md, PI_TEST_PPO_SAC_LMPC.md','전류 → 토크 환산(2.1 N·m/A × 전류), 1.5 A 상한, 인터록 값, 판정 기준'],
   ['motor_sizing_rev11/rmd_ct.json (rmd2.py로 생성)','표 1 시뮬레이션 요구값(armature 0.025 kg·m², 마찰 1배·8배)'],
   ['MyActuator 제품 페이지 (myactuator.pages.dev RMD-X6-P20-60), OpenELAB 판매 페이지','정격 20 N·m, 피크 50 N·m(스톨 시험표 60 N·m), 정격 9.5 A, 피크 29.1 A, 정격 153 rpm, 무부하 176 rpm, Kt 2.1 N·m/A, 정격 320 W, 백래시 10′']],
  widths=[6.5,10.5])
P('가정',bold=True)
for t in ['토크는 모두 출력축 기준이며 지령 전류 × 2.1 N·m/A로 환산했다. 감속기 효율·마찰 손실은 별도로 빼지 않았다.',
          '"운용 상한 3.15 N·m"는 지령 전류 상한에서 환산한 값이다. 스윙업 중 RMD가 실제로 낸 상전류는 로그에서 집계하지 않았다.',
          'PPO·LMPC 암 최고 속도는 로그 그래프에서 읽은 대략값(±0.5 rad/s)이다. 원본 로그(.mat)로 재집계하면 정확한 값을 얻을 수 있다.',
          '피크 토크는 제조사 페이지 표기가 50 N·m(사양표)와 60 N·m(스톨 시험표)로 달라, 보수적으로 50 N·m를 썼다.',
          '정지마찰 0.63 N·m는 전류 단계 시험(0.1/0.3/0.5 A)의 대략값이다. 0.3~0.5 A 사이는 시험하지 않았다.']:
    doc.add_paragraph(t,style='List Bullet')
P('미측정 항목',bold=True)
for t in ['스윙업 중 RMD 보고 상전류의 최대값과 RMS','모터 온도 상승(연속 운전)','회생 시 버스 전압 최대값','각 제어기의 반복 시험 성공률(정책당 최대 3회 시험)']:
    doc.add_paragraph(t,style='List Bullet')
doc.save(D+'RMD-X6_모터_선정_근거_실험값기반.docx'); print('saved')
