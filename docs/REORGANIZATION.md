# 폴더 정리 기록 — 2026-11-12

기존 내용을 삭제하지 않고 다음과 같이 이동했다. 최초 11개 이동 묶음의 105개 파일과 잔여 .DS_Store 2개를 이동 직후 SHA256으로 확인했다. 이후 코드·문서에는 경로 수정을 적용했다. 모델 XML/STL·기존 체크포인트·이미지·TensorBoard 이벤트는 바이트 단위 보존 테스트로 재확인한다.

| 이전 | 현재 |
|---|---|
| Capstone1/Mujoco/files | legacy/mujoco_initial |
| test | models/legacy_cad |
| furuta_rev5_lite_mujoco | models/rev5/source |
| pi | deployment/pi |
| furuta_platform/config.json | configs/rev5_baseline.json |
| furuta_platform/test_contract.py | tests/test_contract.py |
| docs/IO_SPEC.md | docs/interfaces/IO_SPEC.md |
| docs/static_audit.json | docs/reports/static_audit.json |
| docs/validation.txt | docs/reports/validation_initial.txt |
| README-FURUTA.md | README.md |
| __MACOSX | legacy/macos_metadata |
| Capstone1에 남은 .DS_Store | legacy/import_metadata |

변경: 공통 모델/설정 경로, 모델 검사 보고서 출력 경로, Pi import/module 명령, edukit의 메시 검색 경로, 이전 환경의 XML 참조 경로. 이전 학습 로그/체크포인트 저장과 play 정책 검색은 스크립트 위치 기준으로 변경해 실행 디렉터리에 의존하지 않게 했다. 기존 play가 기대하는 CAD 정책이 제공되지 않은 문제는 폴더 이동과 별개이며 임의 정책으로 대체하지 않았다.

추가: pyproject.toml, .gitignore, 폴더별 안내, tests/test_layout.py. 의존성 설치나 Git 저장소 초기화는 수행하지 않았다. 현재는 소스 체크아웃/개발용 editable 설치를 전제로 한다. 별도 wheel에서 models/configs를 제공하는 배포 구성은 아직 없다.

검증: 자동 테스트 총 9개 통과, 관련 Python compileall 통과, CLI 및 Pi replay --help 통과, rev5 정적 분석 재생성(메시 30개 누락 없음). 모든 models XML의 메시 경로와 이동한 모델/체크포인트/이미지/이벤트 파일의 해시 보존 확인. 실제 MuJoCo 모델 로딩·학습·렌더링·edukit 시뮬레이션은 기존 WinError 4551 제한으로 여전히 미검증이다. 실제 통신·하드웨어 구동·펌웨어 업로드 없음.

reports/reorganization_manifest.json은 이동 전 해시와 경로 기록이다. reports/validation_reorganization.txt는 최종 테스트 결과다. tools/reorganize_workspace.py는 이미 실행한 일회성 이동 기록용이며 다시 실행할 필요가 없다(이전 경로 부재/목적지 존재 시 중단).
