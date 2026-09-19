# 와벨헬퍼 — 수업 녹화본 → 필기 자료 파이프라인

의대 수업 녹화(mp4) + 슬라이드 PDF + 작년 필기 PDF를 넣으면, 수업(덱)별로
**필기 가이드 HTML · 태블릿용 단일 HTML · 주석 PDF · 스크립트 MD · 글작성 초안 txt · index.html** 을 만든다.
사용자는 이 산출물을 보며 태블릿에서 슬라이드 위에 손필기를 옮긴다.

## 사용자가 하는 일 (이 순서 그대로 안내한다)

```
cd <repo>  →  claude
/새강의 "폴더이름"      강의 폴더 + timeline.txt 템플릿 생성
  (폴더에 mp4 · 오늘 pdf/pptx · 작년 필기/한장 pdf 넣고, timeline.txt 에 시간만 기입)
/필기 ["폴더이름"]      lecture.json 초안 → 확인 → 파이프라인 → notes 작성 → 빌드·검증
/재빌드 ["폴더이름"]    notes_<key>.json 을 손으로 고친 뒤 build + verify 만 다시
```
스킬 본문은 `.claude/skills/*/SKILL.md`. 절차 변경은 거기서.

## 폴더 규약

```
와벨헬퍼\
  config.json      공통 설정: python(venv), whisper 모델/장치, ffmpeg, 폰트, 렌더 폭
  wabel.cmd        드라이버. ASCII 전용. `wabel --lecture <폴더> [단계…]`
  tools\           모든 스크립트. 강의별 값은 절대 넣지 않는다 (lecture.json 에서 읽는다)
  templates\       timeline.txt · lecture.json.example
  <강의 폴더>\     lecture.json · timeline.txt · mp4 · pdf/pptx · 작년 pdf · _work\ · output\
```
- 강의 폴더명은 자유(한글·공백·쉼표 OK). 덱 `key` 는 **영문 ASCII**(중간파일명·.cmd 인코딩).
- 강의 폴더 찾기: `--lecture <경로>` → `WABEL_LECTURE` → cwd 상위의 `lecture.json`.
- 산출물은 `<강의>\output\`, 중간파일은 `<강의>\_work\`, 로그는 `_work\logs\`.

## 파이썬 / venv

`requirements.txt` 를 설치한 전용 venv 를 쓴다. `wabel.cmd` 의 `PY` 와 `config.json` 의 `python` 을 그 venv 의 python 으로 맞춘다.
- **핀 고정 버전을 올리지 말 것**: ctranslate2 4.6.0(4.7+ 세그폴트), onnxruntime 1.20.1, faster-whisper 1.2.1.
- whisper 모델 캐시는 `HF_HOME` 으로 위치 지정 가능 (large-v3 약 3GB).
- ffmpeg 는 PATH. 폰트는 맑은 고딕(`config.json fonts`, ①②③ 원문자 필요).

## 파이프라인 (`wabel --lecture <폴더> [단계]`, 인자 없으면 audio~post)

| 단계 | 스크립트 | 만드는 것 |
|---|---|---|
| audio | extract_audio.py | `_work/audio/<key>.wav` (16k mono, 구간 = decks[].audio) |
| slides | extract_slides.py (pypdf) | `slides.json` — whisper 프롬프트 용어·페이지 텍스트 |
| pages | render_pages.py all | `_work/pages/`(매칭용) · `output/_slides/`(HTML용) · `_work/lastyear/` |
| transcribe | transcribe.py <key> | `raw/<key>__full.json` (GPU, 105분에 약 35분) |
| detect | slide_detect.py signal/segment | `diff_signal.npy` · `segments.json` |
| match | match_pages.py · check_skipped.py | `segments_matched.json` |
| repair | repair_segments.py | `segments_final.json` (스쳐 간 페이지 복원) |
| cursor | cursor_track.py <key> | `cursor_<key>.json` (마우스 dwell) |
| lastyear | lastyear_map.py | `lastyear_map.json` (올해p → 작년p) |
| post | gap_check → fill_gaps → recheck → assemble → dump_bundle | `bundle_<key>.json` · `worksheet_<key>_a_b.txt` |
| *(수동)* | Claude 가 `notes_<key>.json` 작성 · verify_shots/apply_verify | |
| build | make_script_md · make_html · make_html --tablet · make_pdf · make_writeup · make_index | `output\` |
| verify | verify_final.py | 5항목 점검 (밑줄 글자 미해결·글작성 초안 존재 포함) |

옵션: `--from/--to/--only <단계>` `--decks a,b` `--dry-run` `--out <폴더>`(검증용). `wabel merge <key> [--force]` 는 notes 조각 합치기.

태블릿 HTML(`--tablet`)은 **가로모드 전용**: 왼쪽 좁은 열(29%)에 슬라이드를 작게·sticky 로, 오른쪽에 필기 제안·전문. 원본 슬라이드는 다른 기기에 띄워 두므로 이미지는 `render.tablet`(720px/q72)로 충분하다. 전문 아래 「원 인식」(교정 전 whisper 인식문)은 사용자가 태블릿을 HTML 로 원한 이유이므로 **기본 표시**(버튼으로 숨김만). 배치는 `TABLET_CSS` 한 곳.

## notes_<key>.json (Claude 가 쓰는 파일)

```json
{"pages": [{
  "page": 1,
  "is_new": false,              // 올해 새로 들어온 슬라이드 (lastyear_map 에 대응 없음) → 글작성 '추가페이지'
  "changed": false,             // 작년에도 있었지만 내용이 바뀐 슬라이드 → 글작성 '변경페이지'
  "summary": "이 슬라이드 요지",
  "emphasis": "🔴 교수님이 강조한 것",   // 🔴 로 시작 = 강한 강조(시험·중요 언급) → 글작성 '강조페이지'. 약한 언급은 🔴 없이
  "underline": ["Treponema pallidum",                 // 슬라이드 위 하늘색 밑줄 = 교수님이 읽으신 글줄
                {"text": "clean ulcer", "emph": true},  // 보라색 = 강조
                {"text": "Late", "nth": 2},             // 같은 글자가 여럿이면 몇 번째
                "all"],                                  // 글줄 전부(전부 읽으신 페이지). 보라 항목과 겹치는 줄은 자동 제외
  "notes":     [{"target": "용어", "gloss": "└ 뒤에 붙일 설명"}],
  "pointers":  [{"n": 1, "label": "1번 마커가 가리킨 곳"}],
  "factcheck": [{"quote":"발언","issue":"무엇이 문제","correct":"바른 내용","source":"근거"}],
  "fixes":     [{"ts": "00:12:46", "text": "교정된 문장"}],
  "drops":     ["00:13:01"]     // 갭 보충 중복분 중 사람이 확인해 버릴 것
}]}
```
- worksheet 의 `⚠저확신`·`+보충` 발화를 우선 교정. **fixes 는 타임스탬프로 매칭**(전사를 다시 돌려도 안 어긋남).
- `notes` 는 작년 필기 형식(용어 → └ 설명). 사용자 손필기 관례(와벨 색원칙): **하늘색 밑줄·파란 글씨 = 교수님이 읽으신 부분 전부, 보라색 = 강조**, 초록 "넘어가셨습니다" = 수업하지 않은 슬라이드, 작년 필기 내용은 회색. `emphasis` 에는 보라색으로 갈 것만.
- **`underline`** 은 글자가 있는 슬라이드마다 쓴다: 발화에서 실제로 읽거나 설명한 글줄(구절 단위, 슬라이드 글자 그대로)을 하늘색으로, `emphasis` 에 해당하는 글줄은 `emph: true`. 사진·그림 슬라이드는 비워 둔다(필요하면 `{"rect":[x0,y0,x1,y1]}` 0~1 좌표). 제목 줄은 손필기처럼 보통 긋지 않는다. 글자는 PyMuPDF `search_for` 로 찾으므로 **슬라이드 텍스트와 글자가 같아야** 한다 — 못 찾으면 산출물에 ⚠ 가 뜨고 `verify` 가 실패한다. 판정·좌표는 `tools/overlay.py` 한 곳.
- **말씀 없이 넘어간 페이지**는 `overlay.page_state()` 가 발화 글자수(<6자)로 자동 판정해 HTML·태블릿·PDF 에 초록 「넘어가셨습니다 (n초)」 도장, index·글작성 초안에 목록으로 넣는다. notes 에서 따로 표시할 것은 없다(summary 한 줄은 쓴다).
- 페이지가 많으면 `notes_<key>_A/B/C.json` 으로 나눠 쓰고 `wabel merge <key>`. **최종 notes 가 조각보다 새로우면 merge 가 거부**(검증 반영분 보호) — 의도한 경우만 `--force`.
- 마커 번호 ①②③ 규칙은 `fixes.py dwell_marks()` 한 곳. 마커를 지우면 번호가 밀리므로 `apply_verify` 는 `__DROP__` 을 '(구조 아님)' 라벨로 바꾼다.
- 사진 슬라이드 검증: `verify_shots.py <key>` → `_work/verify_shots/<key>_pNNN.png` 를 직접 보고 라벨 교정 → `patch_add.py`(stdin JSON) → `apply_verify.py <key>`.

## 절대 지킬 것

1. **`lecture.json` 의 `audio.start` 는 전사 후 변경 금지.** wav 의 0초 = 이 값이고 notes 의 `fixes.ts` 가 여기에 매여 있다. 구간을 "깔끔하게" 정규화하면 교정 수백 건이 전부 어긋난다.
2. `extract_slides.py` 는 **pypdf 유지**. pymupdf 로 바꾸면 추출 텍스트 → whisper 프롬프트 → 전사 결과가 달라진다.
3. `tools\` 에 강의 고유 값(파일명·날짜·교수명·구간)을 쓰지 않는다. 필요하면 `lecture.json` 필드를 추가하고 `common.Lecture` 접근자를 만든다.
4. `wabel.cmd` 는 ASCII 만. PS 5.1/.bat 은 BOM 없는 한글을 ANSI 로 읽어 깨진다 — 그래서 드라이버를 Python 으로 옮겼다. 한글 경로는 항상 따옴표.
5. 중간 json(`raw/ segments* cursor_* bundle_* notes_*`)은 지우지 않는다. 지워도 되는 것: `audio/ pages/ lastyear/ frames/ verify_shots/ verify/`(스크립트로 재생성, 오디오는 PCM 까지 동일 확인됨).

## 글작성 초안 (`output\<수업>\글작성_초안_<수업>.txt`)

사용자가 필기·한장·야마를 올릴 때 쓰는 글의 뼈대. `make_writeup.py` 가 notes 에서 뽑는다:
강조페이지 = `emphasis` 가 🔴 로 시작하는 페이지 / 추가페이지 = `is_new` 또는 작년 대응 없음 / 변경페이지 = `changed`.
그 아래 '초안 근거' 에 약한 강조·자동 변경 후보(`lastyear_scores.json` 유사도 낮은 순 최대 6개, 손글씨 많은 페이지도 잡힘)·넘어가신 페이지·팩트체크 페이지를 적는다. 후기·야마 칸은 사람이 쓴다.

## 겪은 함정

- **whisper 갭 보충은 환각을 만든다.** 침묵을 억지로 전사시키면 프롬프트를 되읊거나 "감사합니다" 를 뱉는다. `fill_gaps.py` 의 `_hallucinated`(프롬프트 조각은 `common.prompt_echo_phrases` 가 템플릿에서 유도)·`_dup_of_neighbor` 가 거른다.
- **작년 자료는 페이지가 밀려 있을 수 있다.** (표지 한 장 차이) `lastyear_map.py` 가 DP 로 잡는다. 결과가 이상하면 `--report` 로 보고서를 본다.
- **notes 커버리지**: `verify_final` 4번이 모든 페이지에 notes 가 있어야 통과. 말씀 없이 넘어간 페이지도 `summary` 한 줄은 쓴다.
- 산출물 재빌드 검증: md/html 은 생성 시각이 없어 **바이트 동일**해야 정상, pdf 는 페이지수·텍스트·드로잉 수로 비교.

## 검증 명령

```
wabel --lecture <폴더> --only verify            5항목 + index + 태블릿 HTML 존재
tools\transcribe.py --check --lecture <폴더>    whisper 모델 로드만
wabel --lecture <폴더> --dry-run                 실행될 명령·경로만 출력
```

## 다음에 개선하면 좋은 것 (사용자와 합의 후)

1. 타임라인 반자동(덱 1페이지가 처음 뜨는 시각 제안).
2. verify_shots 를 파이프라인 단계로.
(2026-09-05 완료: 글작성 초안 · 넘어가신 페이지 표시 통일 · `underline` 밑줄 오버레이)
