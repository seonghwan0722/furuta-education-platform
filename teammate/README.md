# 팀원 작업 (MuJoCo SAC · 실기 보정)

팀원이 만든 MuJoCo 기반 SAC 정책과 실기 보정 결과 중 다시 쓰는 데 필요한 것만 담았습니다. 팀원 동의를 받아 올렸습니다.

| 폴더 | 내용 |
|---|---|
| `sim2real_rev11/` | rev11 MuJoCo 모델 도구, SAC 학습(`rl/train_rev11.py`), 지연 환경, 정책 `rl/rev11/sac_rev11.zip`(SB3), 앱 연동 규약 `app/PROTOCOL.md`. 시작은 `SIM2REAL_인수인계.md` |
| `rev11_s2r_calib/` | 실기 보정: 보정 시뮬(`calibrated_sim/`), 식별 파라미터(`params/`), Pi 실행 코드(`pi_host/run_policy.py`, 정책 `actor_rev11.npz`), 평가 결과(`eval/*.json`). 시작은 `README.md`, `인수인계_실기보정.md` |

- 정책 규약은 MATLAB/Pi 정책과 다릅니다: 50 Hz, 관측 6개, 진자 매달림 = 0, 1 N·m(1.2 A) 기준. 자세한 비교는 [docs/handoff/HANDOFF_다른AI용.md](../docs/handoff/HANDOFF_다른AI용.md) §3.3.
- 제외한 것: 실물 원시 로그 CSV(약 20 MB), 그림·GIF, `changes/*.diff`, `handoff/`(= `sim2real_rev11/`과 같은 사본), Pi 세션 상태 파일.
- rev11 메시(STL)는 중복을 피해 `python_handoff/rev11_model/meshes/`에만 둡니다. XML을 열 때는 그 폴더를 `meshes/`로 복사하거나 `FURUTA_REV11_XML`로 `python_handoff/rev11_model/furuta_rev11_bent_with_tip.xml`을 가리키세요.
- `rev11_s2r_calib/CLAUDE.md`는 팀원이 AI 작업에 쓰던 지시문입니다. 참고용입니다.
- 일부 스크립트에 팀원 PC 경로(`C:\Users\...`)가 하드코딩되어 있습니다. 실행 전 경로를 바꾸세요.


## furuta-pendulum-rl (2026-11-28 추가)

팀원 저장소 [sjh030619-boop/furuta-pendulum-rl](https://github.com/sjh030619-boop/furuta-pendulum-rl)의 최신 커밋 `5cf850e`(11/25)을 [`furuta-pendulum-rl/`](furuta-pendulum-rl/IMPORT_NOTE.md)에 넣었습니다. 앱(`app/`)은 `pendulum_studio/`에 이미 확장판이 있어 제외했고, SB3 zip 체크포인트도 용량 때문에 뺐습니다.
