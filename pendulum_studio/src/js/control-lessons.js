/* Classroom explanations aligned with control-core.js. These are not controller implementations. */
(function (PS) {
  'use strict';
  const content = {
    pid: `
      <div class="lesson-detail-group">
        <section class="card theory-card">
          <span class="pill agent">PID · 비례 / 적분 / 미분</span>
          <h3>같은 기울기라도, 지나온 과정과 움직이는 방향을 함께 봐요</h3>
          <p><b>P</b>(Proportional)는 지금의 오차, <b>I</b>(Integral)는 쌓인 오차, <b>D</b>(Derivative)는 오차가 바뀌는 빠르기에 반응합니다. 세 역할을 더해 명령을 만듭니다.</p>
          <p class="theory-note">이 진자는 팔도 함께 움직입니다. 그래서 이 앱은 진자 PID에 <b>팔 위치·속도 피드백</b>을 더합니다. ‘P만’ 설정에서도 팔 피드백은 남아 있어요.</p>
          <div data-explainer="pid"></div>
        </section>
        <section class="card theory-card">
          <h3>세 항이 각각 어떤 정보를 볼까요?</h3>
          <div class="theory-grid">
            <div><span class="pill state">P · 지금</span><h4>얼마나 벗어났나요?</h4><p>직립과의 차이가 크면 P항의 크기도 커집니다. P 배율을 높이면 같은 오차에 더 크게 반응합니다.</p><p class="theory-note">너무 강하면 힘의 상한에 자주 닿거나 흔들림이 커질 수 있습니다.</p></div>
            <div><span class="pill reward">I · 누적</span><h4>오차가 계속 남나요?</h4><p>작은 오차도 같은 방향으로 오래 남으면 누적됩니다. 지속적인 편차를 줄이는 데 쓰지만, 과거 오차가 오래 남아 지나치게 반응할 수도 있습니다.</p><p class="theory-note">오차가 0이 된 순간에도 쌓인 값이 남아 있으면 I항은 0이 아닐 수 있어요.</p></div>
            <div><span class="pill action">D · 변화</span><h4>어느 쪽으로 얼마나 빨리 가나요?</h4><p>현재 기울기가 같아도 직립에서 멀어지는 중인지, 돌아오는 중인지 구분합니다. 적절한 D항은 진동을 줄이는 데 도움을 줍니다.</p><p class="theory-note">D를 높인다고 항상 좋아지지는 않습니다. 측정 속도의 잡음에도 민감해집니다.</p></div>
          </div>
        </section>
        <section class="card theory-card">
          <h3>이 앱은 이런 순서로 힘을 정해요</h3>
          <ol class="theory-steps"><li><b>네 상태 읽기</b><p>팔 각도 θ, 직립 오차 φ, 팔 각속도 θ̇, 진자 각속도 φ̇를 읽습니다.</p></li><li><b>항별 명령 더하기</b><p>P + I + D에 팔이 제자리에서 멀리 떠나지 않도록 하는 피드백을 더합니다.</p></li><li><b>누적과 힘 제한 적용</b><p>I가 포화 방향으로 더 쌓이지 않게 조절하고, 합친 명령을 설정한 힘의 상한 안으로 제한합니다.</p></li></ol>
          <div class="theory-equation">요청 명령 = P항 + I항 + D항 + 팔 피드백<br>적용 명령 = 요청 명령을 −상한 ~ +상한으로 제한</div>
          <p class="theory-note">그래프의 ‘P · I · D가 만든 힘’에서는 제한 전 각 항을 볼 수 있습니다. 여러 항이 서로 상쇄될 수도 있어요. ‘모터 명령’ 그래프는 상한을 적용한 뒤의 값입니다.</p>
          <details class="theory-details"><summary>수식과 이 앱의 실제 게인 연결 보기</summary>
            <p>이 화면은 목표를 0으로 두고 <b>φ = 측정 기울기 − 목표</b>로 씁니다. φ는 라디안, φ̇는 rad/s입니다. 기준 상태 피드백 게인을 K̄라고 하면 다음과 같이 계산합니다.</p>
            <div class="theory-equation">P항 = −K̄<sub>φ</sub> · p · φ<br>I항 = −K̄<sub>φ</sub> · i · z<br>D항 = −K̄<sub>φ̇</sub> · d · φ̇<br>팔 피드백 = −K̄<sub>θ</sub>θ − K̄<sub>θ̇</sub>θ̇<br>u<sub>요청</sub> = P항 + I항 + D항 + 팔 피드백</div>
            <p><b>p, i, d는 설정 슬라이더의 배율</b>입니다. 예를 들어 P=2.0배는 기준 P계수의 두 배라는 뜻이며, 물리 단위를 가진 게인 자체가 2라는 뜻은 아닙니다. 부호는 이 장치의 좌표계를 포함한 기준 게인에 들어 있습니다.</p>
            <p>기준 K̄는 Q = diag(0.5, 40, 0.3, 1), R = 1의 LQR 설계에서 가져옵니다. LQR 화면의 Q/R을 바꿔도 PID의 이 기준은 바뀌지 않습니다. 기본값 p=1, i=0, d=1에서는 기준 LQR과 같은 피드백 식이 됩니다.</p>
            <div class="theory-equation">누적 후보 z* = clip(z<sub>이전</sub> + φΔt, −1, 1)</div>
            <p>누적 제한을 켜면 요청 명령이 상한 안에 있거나, I의 변화가 포화를 풀어 주는 방향일 때만 후보를 채택합니다. 그 외에는 이전 z를 유지합니다. 이것이 이 앱의 <b>조건부 적분(anti-windup)</b>입니다. 체크를 꺼도 누적값 자체의 −1~1 제한은 유지됩니다.</p>
          </details>
        </section>
        <section class="card theory-card">
          <h3>먼저 이 차이를 찾아보세요</h3>
          <div class="theory-table-wrap" tabindex="0" role="region" aria-label="PID 비교 실험의 관찰점"><table><thead><tr><th>바꿀 것</th><th>먼저 예상하기</th><th>그래프에서 확인하기</th></tr></thead><tbody><tr><td>P만 → P + D</td><td>빠르게 돌아오는 순간에는 어떤 차이가 날까?</td><td>기울기가 0을 지나치는 정도와 진동</td></tr><tr><td>P + D → I 추가</td><td>계속 남는 작은 편차가 있다면?</td><td>I항의 누적과 기울기의 장기 변화</td></tr><tr><td>힘 상한 낮추기</td><td>원하는 힘을 모두 낼 수 없다면?</td><td>상한 도달 비율과 누적 제한의 역할</td></tr></tbody></table></div>
          <p class="theory-note">같은 시작각과 환경에서 한 가지씩 바꾸세요. P·I·D를 모두 크게 만드는 것이 목표는 아닙니다.</p>
        </section>
      </div>`,
    lqr: `
      <div class="lesson-detail-group">
        <section class="card theory-card">
          <span class="pill agent">LQR · 선형 이차 조절기</span>
          <h3>기울기·팔 위치·속도·힘을 하나의 비용으로 함께 평가해요</h3>
          <p><b>Linear</b>는 설계에 선형 모델을 쓴다는 뜻, <b>Quadratic</b>은 오차와 명령을 제곱해 비용을 만든다는 뜻, <b>Regulator</b>는 목표 상태 근처에 머물게 하는 제어기라는 뜻입니다.</p>
          <p>‘진자는 빨리 세우고 싶지만 힘은 아끼고 싶다’처럼 여러 목표가 부딪힙니다. <b>Q와 R으로 중요도를 정하면</b> 모델을 이용해 상태 피드백 게인 K를 계산합니다.</p>
          <div data-explainer="lqr"></div>
        </section>
        <section class="card theory-card">
          <h3>Q와 R은 게인 자체가 아니라, 설계의 평가 기준이에요</h3>
          <div class="theory-grid">
            <div><span class="pill state">Q · 상태 비용</span><h4>어떤 상태를 더 줄일까요?</h4><p>진자 기울기, 팔 위치, 두 각속도에 각각 비용을 줍니다. 진자 Q를 높이면 다른 조건이 같을 때 기울기 오차를 더 비싸게 평가합니다.</p></div>
            <div><span class="pill action">R · 입력 비용</span><h4>힘을 얼마나 아낄까요?</h4><p>같은 모터 명령에도 R이 크면 더 큰 비용이 붙습니다. 설계에서 힘 사용을 더 부담스럽게 보도록 바꾸는 것입니다.</p></div>
          </div>
          <p class="theory-note">Q/R을 바꾸면 새 K가 계산됩니다. 실제 오차가 반드시 작아지거나 힘이 반드시 단조롭게 줄어드는 것은 아닙니다. 입력 포화와 비선형 움직임까지 포함한 실험 결과로 확인하세요.</p>
          <div class="theory-equation">한 순간의 비용 = 상태 오차 비용 + 힘 사용 비용<br>ℓ(x, u) = xᵀQx + Ru²</div>
          <p>제곱을 쓰면 양수·음수 오차가 서로 지워지지 않고 큰 오차를 더 크게 평가합니다. 비용은 선택한 기준의 숫자이며, 전기 소비량을 그대로 뜻하지는 않습니다.</p>
        </section>
        <section class="card theory-card">
          <h3>설계할 때와 실행할 때 하는 일이 달라요</h3>
          <ol class="theory-steps"><li><b>설계: 직립 근처를 선형화</b><p>작은 상태·입력 변화가 다음 상태를 얼마나 바꾸는지 계산해 A, B를 구합니다. 앱에서는 비선형 모델의 한 제어 주기 응답을 수치적으로 선형화합니다.</p></li><li><b>설계: Q/R에서 K 계산</b><p>선형 모델의 미래 비용 합을 줄이는 K를 Riccati 방정식으로 구합니다. 신경망 학습을 하는 과정은 아닙니다.</p></li><li><b>실행: 현재 상태에 K 적용</b><p>매 주기 네 상태를 읽고 u = −Kx를 계산합니다. 그 명령을 상한으로 제한해 비선형 진자 모델에 전달합니다.</p></li></ol>
          <div class="theory-equation">x = [θ, φ, θ̇, φ̇]ᵀ<br>u<sub>요청</sub> = −K<sub>θ</sub>θ − K<sub>φ</sub>φ − K<sub>θ̇</sub>θ̇ − K<sub>φ̇</sub>φ̇</div>
          <p class="theory-note">실행 중 미래 궤적을 매번 탐색하는 방식은 아닙니다. 미래 비용을 고려해 미리 설계한 K가 현재 상태를 입력받습니다. ‘상태별 피드백이 만든 힘’에서 네 항의 기여를 확인하세요.</p>
          <details class="theory-details"><summary>이산 LQR의 목적함수와 제한의 의미 보기</summary>
            <div class="theory-equation">x<sub>k+1</sub> = Ax<sub>k</sub> + Bu<sub>k</sub><br>J = Σ<sub>k=0…∞</sub>(x<sub>k</sub>ᵀQx<sub>k</sub> + Ru<sub>k</sub>²)<br>Q = diag(Q<sub>팔</sub>, Q<sub>진자</sub>, 0.3, 1)<br>u<sub>k</sub> = −Kx<sub>k</sub></div>
            <p>Q의 순서는 팔 각도, 진자 직립 오차, 팔 각속도, 진자 각속도입니다. 이 화면에서 두 각속도의 가중치 0.3과 1은 고정이며, ‘팔 Q’와 ‘진자 Q’, R만 바꿉니다.</p>
            <p>식의 ∞는 설계에서 무한한 미래 비용을 고려한다는 뜻입니다. 화면의 실험은 10초입니다. 이 앱의 LQR 설계에는 힘의 상한이 들어가지 않고, <b>실행 명령을 계산한 뒤 잘라 냅니다.</b> 따라서 포화가 생긴 실제 실행은 상한 없는 선형 문제의 최적해와 달라질 수 있습니다.</p>
            <p>직립 근처의 선형 모델로 설계하지만 실험은 비선형 모델로 합니다. 큰 각도, 마찰, 센서 오차 같은 영향 때문에 선형 설계의 성질이 모든 자세에서 그대로 보장되지는 않습니다.</p>
          </details>
        </section>
        <section class="card theory-card">
          <h3>오차 하나만 보고 좋은 제어라고 판단하지 마세요</h3>
          <div class="theory-table-wrap" tabindex="0" role="region" aria-label="LQR 비교 실험의 관찰점"><table><thead><tr><th>한 가지만 바꾸기</th><th>예상할 절충</th><th>함께 볼 값</th></tr></thead><tbody><tr><td>진자 Q 높이기</td><td>진자 기울기를 더 비싸게 평가</td><td>기울기 오차 · 힘 RMS · 상한 도달</td></tr><tr><td>팔 Q 높이기</td><td>팔의 시작 위치 이탈을 더 비싸게 평가</td><td>팔 움직임 · 진자 균형의 변화</td></tr><tr><td>R 높이기</td><td>같은 입력 사용의 비용 증가</td><td>힘 RMS · 오차 · 종료 여부</td></tr></tbody></table></div>
          <p class="theory-note">기본 PD와 기본 LQR이 같게 보일 수 있습니다. 이 앱의 기본 PD는 같은 기준 K에서 시작하도록 구성되어 있습니다.</p>
        </section>
      </div>`,
    lmpc: `
      <div class="lesson-detail-group">
        <section class="card theory-card">
          <span class="pill agent">LMPC · 선형 모델 예측 제어</span>
          <h3>미래의 명령들을 계획하되, 지금 필요한 첫 명령만 써요</h3>
          <p><b>Linear Model Predictive Control</b>입니다. 선형 모델로 앞으로 N칸의 상태를 예측하고, 오차와 힘의 비용을 함께 줄이는 명령 묶음을 찾습니다. 이때 <b>각 명령이 힘의 상한을 지키도록</b> 계획에 조건을 넣습니다.</p>
          <p>계획을 끝까지 그대로 재생하지 않습니다. 한 번 움직인 뒤 상태를 다시 읽고 미래를 새로 계산해요.</p>
          <div data-explainer="lmpc"></div>
        </section>
        <section class="card theory-card">
          <h3>예측 → 계획 → 첫 명령 → 다시 측정</h3>
          <ol class="theory-steps"><li><b>현재를 출발점으로 삼기</b><p>현재 상태 x₀에서 시작합니다. x₀는 이전에 예측했던 값이 아니라 이번 주기에 읽은 상태입니다.</p></li><li><b>N개 명령과 그 결과를 함께 계산</b><p>u₀, u₁, …, u<sub>N−1</sub>을 후보로 두고 x₁부터 x<sub>N</sub>까지의 기울기·팔 위치·속도를 예측합니다. 비용을 줄이되 |u| ≤ 상한을 지키는 계획을 찾습니다.</p></li><li><b>u₀만 실제로 적용</b><p>나머지는 다음 상태가 어떻게 될지 예측하기 위한 계획입니다. 새 상태를 읽으면 시간을 한 칸 옮겨 다시 풉니다.</p></li></ol>
          <p class="theory-note">그래프 탭의 점선은 이 선형 모델의 예측이며, 앞으로 실제로 일어날 일을 보장한 선이 아닙니다. 실제 움직임은 비선형 모델과 센서·마찰 조건의 영향을 받습니다.</p>
        </section>
        <section class="card theory-card">
          <h3>Q·R·N·힘 상한은 각각 다른 역할이에요</h3>
          <div class="theory-table-wrap" tabindex="0" role="region" aria-label="LMPC 설정의 의미"><table><thead><tr><th>설정</th><th>바뀌는 것</th><th>주의해서 볼 점</th></tr></thead><tbody><tr><td>Q / R</td><td>상태 오차와 힘 사용의 비용</td><td>허용 여부가 아니라 선호하는 정도</td></tr><tr><td>N · 예측 길이</td><td>계획에 포함하는 미래 칸 수</td><td>길어지면 계산량도 증가</td></tr><tr><td>힘의 상한</td><td>계획의 각 명령이 지켜야 할 범위</td><td>힘이 부족하면 긴 예측만으로 해결되지 않음</td></tr></tbody></table></div>
          <div class="theory-equation">한 칸 = 0.02초<br>앞을 보는 시간 = N × 0.02초<br>예: N = 20 → 0.40초</div>
          <p class="theory-note">예측 길이는 전체 실험 시간과 다릅니다. 10초 실험 동안 짧은 미래를 반복해서 봅니다. N을 크게 한다고 반드시 더 잘 서는 것은 아닙니다.</p>
          <details class="theory-details"><summary>이 앱의 목적함수·제약·종단 비용 보기</summary>
            <p>현재 상태 x₀가 주어지면 다음 N개 입력을 결정합니다. 코드가 최소화하는 비용을 그대로 쓰면 다음과 같습니다.</p>
            <div class="theory-equation">최소화 J = Σ<sub>j=1…N−1</sub> x<sub>j</sub>ᵀQx<sub>j</sub><br>　　　　+ Σ<sub>j=0…N−1</sub> Ru<sub>j</sub>² + x<sub>N</sub>ᵀPx<sub>N</sub><br>조건: x<sub>j+1</sub> = Ax<sub>j</sub> + Bu<sub>j</sub><br>　　　−상한 ≤ u<sub>j</sub> ≤ +상한<br>실행: 첫 입력 u₀만 적용</div>
            <p>현재 상태 비용 x₀ᵀQx₀를 더해 쓰는 자료도 있습니다. 이미 x₀가 고정되어 있어 이 항을 더해도 선택되는 입력은 같아요.</p>
            <p><b>P는 마지막 상태의 종단 비용</b>입니다. 예측 끝 이후의 비용도 고려하도록 같은 Q/R의 LQR 해를 사용합니다. PID의 P항과는 다른 기호예요. Q는 LQR과 같은 순서인 diag(Q<sub>팔</sub>, Q<sub>진자</sub>, 0.3, 1)입니다.</p>
            <p>이 계산은 목적함수가 이차식이고 제약이 선형인 <b>이차계획법(QP)</b> 문제입니다. 앱은 제한 안의 해를 유지하며 반복 계산하고, 허용 오차에 도달하지 못한 주기는 기록에 알립니다. 그때의 결과는 수렴을 확인한 최적해로 해석하지 않습니다.</p>
          </details>
        </section>
        <section class="card theory-card">
          <h3>LQR과 같을 때도 있고, 다른 이유도 있어요</h3>
          <div class="theory-grid"><div><span class="pill agent">LQR</span><p>상한 없는 선형 문제에서 K를 설계합니다. 이 앱은 실행할 때 u = −Kx를 계산한 다음 상한으로 자릅니다.</p></div><div><span class="pill action">LMPC</span><p>미래의 각 입력이 상한을 지키도록 포함해 계획을 다시 풉니다. 상한에 닿기 전부터 이후의 영향을 함께 고려할 수 있습니다.</p></div></div>
          <p class="theory-note">같은 모델·Q/R·LQR 종단 비용을 쓰고 입력 제약이 작동하지 않으면 두 방식은 같은 명령을 낼 수 있습니다. LMPC가 언제나 더 좋은 결과를 내는 것은 아닙니다.</p>
          <p>이 앱의 QP에는 <b>각도·속도 제약이 들어 있지 않습니다.</b> 속도나 기울기 한계에 닿으면 별도의 실험 종료 조건이 작동합니다. 예측기가 이 한계를 미리 지키도록 보장하는 구조와 구분하세요.</p>
          <div class="theory-equation">비교해 보기: 같은 시작각·Q/R에서<br>N만 바꾸기 → 기록하기 → 힘 상한만 바꾸기</div>
          <p class="theory-note">오차와 힘뿐 아니라 실험이 10초를 끝냈는지, QP 계산이 허용 오차에 도달했는지도 함께 읽어 보세요.</p>
        </section>
      </div>`
  };

  PS.ControlLessons = {
    show(method) {
      const host = document.getElementById('controllerLesson');
      if (!host || !Object.prototype.hasOwnProperty.call(content, method)) return;
      host.innerHTML = content[method];
      host.setAttribute('aria-label', method.toUpperCase() + ' 제어 방식의 자세한 설명');
      const panel = document.getElementById('overviewPanel');
      if (panel) panel.scrollTop = 0;
      const visual = host.querySelector('[data-explainer]');
      if (visual && PS.ControlExplainers) PS.ControlExplainers.mount(method, visual);
    }
  };
})(window.PS = window.PS || {});
