# 모델 rev5 원본

`source/`에는 사용자가 제공한 furuta_rev5_lite_mujoco.xml 및 meshes/를 변경 없이 보관한다. 모델명과 메시 파일명은 출처 추적을 위해 유지했다.

단위·관절·COM 점검은 ../../docs/FURUTA_PLATFORM.md 및 ../../docs/reports/static_audit.json 참조. 질량/관성은 CAD 기재값이며 실측이 아니다. 현재 GL35/24V/D안/rev11 장치와 동일하다고 가정하지 않는다. RMD 모터 등 이전 구성 메시가 포함되어 있다.

학습용 옵션/actuator는 furuta_platform.common.model_xml이 메모리에서 추가한다. 원본은 직접 수정하지 않는다. MuJoCo DLL 정책 차단으로 컴파일 미검증.
