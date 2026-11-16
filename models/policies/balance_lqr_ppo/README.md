# GUI 기본 균형 정책

원래 실행 이름은 `balance_lqr_ppo_s42`입니다. LQR 행동을 모방한 모델을 초기값으로 두고, `configs/rev5_shaped_balance_low_noise.json`의 보상과 초기화 조건으로 PPO를 8,192 스텝(시드 42) 학습했습니다. 학습 체크포인트의 SHA-256은 `147cd2d0dea4dfd33d21333aa13e3a4ad4f3f56e07d82e1e1fea27242dc9750d`입니다.

MuJoCo 기본 물리 조건에서 직립 부근에서 출발한 20개 결정론적 평가 에피소드가 모두 제안 기준(직립 오차 10° 이내, 진자 속도 1 rad/s 이내, 연속 2초)을 통과했습니다. 이 결과는 스윙업이나 실물 균형 성능을 검증하지 않습니다.

`actor.npz`는 PyTorch 없이 NumPy로 읽는 추론용 가중치입니다. `manifest.json`에는 해시, 학습 설정 및 입출력 규약이 있습니다. 학습을 이어서 실행하려면 원래 PPO 체크포인트가 필요합니다.
