# 와벨헬퍼

수업 녹화본(mp4)과 슬라이드 PDF, 작년 필기 PDF를 넣으면 수업별 필기 자료를 만들어 주는 도구.
Claude Code 와 함께 쓴다 (`CLAUDE.md` 가 Claude 용 절차서).

## 결과물 (`<강의 폴더>\output\index.html` 을 열면 입구)

수업(덱)마다
1. **필기 가이드 HTML** — 슬라이드 한 쪽마다 요지 · 교수님 강조 · 작년 형식 필기 제안 · ⚠ 팩트체크 · 마우스로 짚은 곳(빨간 번호) · 말씀 전문. 슬라이드 이미지는 `output\_slides\` 참조.
2. **태블릿용 HTML** (`…_태블릿.html`) — 이미지를 내장한 **파일 하나**. iPad 파일앱/갤럭시탭에서 바로 열린다. **가로모드** 기준: 왼쪽 좁은 열에 슬라이드(작게, 스크롤해도 고정), 오른쪽 넓은 열에 필기 제안·전문. 교정 전 인식문 「원 인식」이 기본으로 보이고 버튼으로 숨길 수 있다.
3. **주석 PDF** — 원본 슬라이드 오른쪽 단에 같은 내용, 슬라이드 위에 포인팅 번호.
4. **스크립트 MD** — 전문. 문장 앞 ①②③ = 그때 짚고 있던 지점. 맨 뒤에 확정 못 한 구간 목록.
5. **글작성 초안 txt** — 올릴 때 쓰는 글의 뼈대(강조페이지·추가페이지·변경페이지 목록 자동, 후기·야마는 직접).

슬라이드 위 표시는 손필기 색 규칙과 같다: **하늘색 밑줄** = 교수님이 읽으신 부분, **보라색 밑줄** = 강조,
초록 **「넘어가셨습니다」** = 말씀 없이 지나간 슬라이드. (HTML·태블릿·PDF 모두 동일)

## 사용법

```
cd <repo>
claude
/새강의 "피부감각기_피부종양, STD, 전신질환의 피부증상(결체조직질환)"
   → 폴더에 mp4 · 오늘 pdf/pptx · 작년 필기·한장 pdf 를 넣고 timeline.txt 에 시간만 채운다
/필기 "폴더이름"        (폴더가 하나면 이름 생략 가능)
/재빌드 "폴더이름"      notes 를 손으로 고친 뒤 산출물만 다시
```

직접 돌릴 때: `wabel --lecture "<폴더>" [단계…]` (`wabel stages` 로 단계 목록, `--dry-run` 으로 명령만 보기).

## 구성

| 경로 | 내용 |
|---|---|
| `config.json` | 공통 설정 — python(전용 venv), whisper 모델(large-v3)/장치, ffmpeg, 폰트, 렌더 폭 |
| `wabel.cmd` | 드라이버 (`tools\pipeline.py`) |
| `tools\` | 스크립트. 강의별 값은 없다 — 각 강의의 `lecture.json` 을 읽는다 |
| `templates\` | `timeline.txt`, `lecture.json.example` |
| `.claude\skills\` | `/새강의` `/필기` `/재빌드` |
| `<강의 폴더>\` | `lecture.json` + 자료 + `_work\`(중간파일·로그) + `output\` |

## 환경

- Python: `<venv>` . 필요한 패키지는 `requirements.txt` 참고.
- GPU: faster-whisper large-v3, cuda/float16 (RTX 3070 8GB 에서 105분 강의 약 35분). 실패 시 CPU int8 폴백.
- ffmpeg (PATH), 맑은 고딕 폰트.

## 파이프라인 한눈에

```
mp4 ─ffmpeg─▶ wav ─faster-whisper─▶ raw 전사 ─갭검사/보충/재확인─▶
pdf ─pypdf──▶ slides.json(용어 프롬프트)                              ├─ assemble ─▶ bundle_<key>.json ─▶ worksheet
mp4 ─프레임 차분─▶ 슬라이드 구간 ─이미지 매칭+DP─▶ 페이지 ─8fps 재탐색─▶ 복원   │
mp4 ─배경 차분─▶ 마우스 dwell ──────────────────────────────────────────────┘
작년 pdf ─이미지 DP─▶ lastyear_map.json
worksheet ─Claude─▶ notes_<key>.json ─build─▶ HTML · 태블릿 HTML · PDF · MD · 글작성 초안 · index
```

자세한 규칙·함정은 `CLAUDE.md`.
