# 정책 학습 이력

정책 파일명은 policy.zip, 내보낸 actor는 actor.npz 그대로 사용한다. 파일명 대신 SHA256과 training_id로 정확한 정책을 구분한다. 새 CLI 학습부터 자동 기록하며 기존 파일에 과거 이력을 소급 생성하지 않는다.

## 저장 위치

```text
runs/<실험명>/
  policy.zip
  policy.zip.metadata.json       # 최신 저장 영수증 + 자체 포함 학습 조건
  training.json                  # 현재 학습 상태·완료/중단·실제 학습량
  history/<training_id>/
    training_start.json          # 시작 시점 설정·알고리즘·버전·출처
    training_end.json            # 최종 상태(완료/실패/중단)
    code/furuta_platform/*.py    # 실행 시작 시점 코드 사본
    artifacts/<receipt_id>.json # 저장할 때마다 새로 생성되는 영수증
  checkpoints/
    policy_<step>_steps.zip
    policy_<step>_steps.zip.metadata.json
  export/
    actor.npz
    manifest.json                # 원본 policy 해시·training_id·학습 기록 포함
```

기록 내용: 한국 시간 ISO 저장 시각, 학습 목적 메모, seed, 요청/실제 step 수, PPO 하이퍼파라미터와 정책 구조, 보상·초기조건·물성·안전 제한을 포함한 전체 설정, Python/라이브러리 버전, 실행 명령, 코드 사본/해시, 원본 XML 및 STL 해시, Git commit(저장소가 아니면 null), 부모 정책 해시/ID, 부모 대비 설정/코드 변경, 저장 당시 optimizer update 수.

모든 실제 gradient update마다 가중치를 저장하는 방식은 아니다. 중간 체크포인트와 최종 **파일 저장 시점마다** 기록한다. optimizer update 카운터는 부모에서 이어받은 횟수까지 포함하므로 학습 환경 step 수와 구분한다. 체크포인트는 rollout 수집 도중 저장될 수 있고 그 rollout의 PPO update 전일 수 있다. 실제 최종 step 수는 SB3 rollout 단위 때문에 요청보다 클 수 있다.

새 run은 이전과 같이 고유 폴더를 사용하며 이미 있는 폴더는 덮어쓰지 않는다. 같은 policy.zip 이름이어도 각 run의 ID/해시로 구분한다. 이력 모듈은 동일 경로에 새 정책을 기록해도 과거 영수증을 보존하지만, 가중치의 자동 복구/과거 파일 보관 기능은 아니다. 이전 정책을 유지하려면 해당 run/체크포인트를 보존해야 한다. 이력 JSON과 해시는 암호학적 서명이 아니며 수정 방지를 보증하지 않는다.

## 사용 예

```powershell
.venv/Scripts/python.exe -m furuta_platform.cli train --config configs/rev5_shaped_balance.json --run runs/balance_v2_s42 --steps 100000 --seed 42 --note "직립 시작으로 균형 보상 검증" --checkpoint-every 10000

.venv/Scripts/python.exe -m furuta_platform.cli train --config configs/rev5_shaped_mixed.json --run runs/mixed_v2_s42 --initialize-from runs/balance_v2_s42 --steps 200000 --seed 42 --note "직립 시작 100%에서 직립/아래 50%씩으로 변경"
```

누적 step 수는 기록이 있는 부모부터 정확히 연결한다. 과거 정책에 metadata가 없으면 누적 step은 null(미상), parent.provenance=not_recorded로 남긴다. 그 정책이 학습되지 않았거나 0 step이라는 뜻이 아니다. 알려진 현재 단계 학습량은 stage_steps로 따로 기록한다.

평가/내보내기/이어학습 전에 기존 sidecar가 있으면 실제 policy 해시와 대조한다. 불일치하면 중단한다. 파일만 외부 도구로 덮어쓰고 이전 metadata를 남기는 실수를 검출하기 위한 기능이다.

정책을 복사할 때 zip과 metadata를 함께 복사하고, 전체 재현이 필요하면 run 폴더 및 해당 버전 models/ 자산도 보관한다. export/는 manifest에 학습 기록을 포함하지만 전체 코드와 메시까지 포함하는 배포 묶음은 아니다. 기존 정책은 기록 부재를 명시하고 사용 가능하게 두었다.

## 검증

- 전체 18개 테스트 통과: 같은 파일명으로 두 번 기록해도 과거 영수증 유지, 해시 변조 검출, 부모 누적 step/설정 변경, 이전 기록 없는 부모 처리 포함.
- 실제 PPO 512 step → 부모를 이어받아 추가 512 step. 각 단계에서 256 step 간격 체크포인트 2개 + 최종 영수증 1개 확인, 자식 누적 1024 step 확인.
- 평가/내보내기에 동일 정책 해시 연결, export 100개 입력 parity 통과.
- 학습 이력 연결 검증이며 정책 성능 검증은 아니다. 결과: ../reports/provenance_smoke_20261112.json.
