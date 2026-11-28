# 팀원 저장소 가져오기 기록

- 원본: [sjh030619-boop/furuta-pendulum-rl](https://github.com/sjh030619-boop/furuta-pendulum-rl), 최신 커밋 [`5cf850e`](https://github.com/sjh030619-boop/furuta-pendulum-rl/commit/5cf850ec226652896cc01eba5b3cd7d49f61503a) (2026-11-25, "Install guide: the repository is public now")
- 앱 설치 파일: [v0.2.0 릴리스](https://github.com/sjh030619-boop/furuta-pendulum-rl/releases/tag/v0.2.0)
- 가져온 날: 2026-11-28

## 뺀 것
- `app/`: 같은 커밋을 바탕으로 확장한 수업용 앱이 이미 [`pendulum_studio/`](../../pendulum_studio/README.md)(0.3.0-classroom)에 있어서, 덮어쓰지 않도록 넣지 않았습니다. 원본 `app/`에만 있는 것은 `preview/`와 `design/mockup*.html`뿐입니다.
- SB3 체크포인트 `*.zip` 246개(약 55 MB)와 GIF: 용량 때문에 뺐습니다. 원본 저장소에서 받으면 됩니다. numpy 정책(`*.npz`)은 넣었습니다.
- 학습 로그(`*.log`, `logs/`): 이 저장소 `.gitignore` 규칙에 따라 빠졌습니다.

그 밖의 파일(`rl/`, `s2r/`, `meshes/`, rev18b MuJoCo 모델, 도구, 인수인계 문서)은 원본 그대로입니다.
