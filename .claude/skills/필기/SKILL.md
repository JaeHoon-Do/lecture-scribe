---
name: 필기
description: 강의 폴더 하나를 끝까지 처리한다 — timeline.txt 로 lecture.json 작성(확인) → wabel 파이프라인(오디오·전사·슬라이드 매칭·포인팅·조립) → notes_<key>.json 작성 → 사진 슬라이드 검증 → 빌드·검증 → 보고. "/필기 [폴더이름]" 또는 "필기 자료 만들어" 라고 할 때.
---

# /필기 [폴더이름]

한 강의를 산출물까지 자동으로 진행한다. 중간에 사용자 확인이 필요한 곳은 **2번(파일 매칭)** 뿐이다.
전체 규칙은 `CLAUDE.md` 를 따른다. 이미 끝난 단계의 산출물이 있으면 건너뛰고 이어서 한다(재개 가능).

`W` = `<repo>`, `PY` = `python`.
스크립트는 `"$PY" "$W\tools\<스크립트>" <인자> --lecture "<폴더>"` 로, 단계는 `"$W\wabel.cmd" --lecture "<폴더>" <단계>` 로 부른다. 경로는 항상 따옴표.

## 1. 강의 폴더 확정
- 인자 `$ARGUMENTS` 가 있으면 `W\<인자>`.
- 없으면 `W` 바로 아래 폴더 중 `timeline.txt` 는 있고 `output\index.html` 은 없는 폴더가 **하나뿐이면** 그것, 아니면 AskUserQuestion 으로 고른다.
- `timeline.txt` 와 mp4 가 없으면 무엇이 빠졌는지 알려 주고 멈춘다.

## 2. lecture.json 만들기 (사용자 확인 필수)
`lecture.json` 이 이미 있고 `_work\raw\` 에 전사본이 있으면 **이 단계를 건너뛴다** (`audio.start` 변경 금지).

1. `timeline.txt` 파싱: `#` 줄 무시, `HH:MM:SS ~ HH:MM:SS  이름` 줄만. 이름이 `수업이름1` 처럼 템플릿 그대로면 채워 달라고 하고 멈춘다.
2. 폴더 파일 목록으로 채운다:
   - `mp4` = 폴더의 유일한 mp4. 파일명 `YYYYMMDD_교시_과목_교수` 에서 `date`(YYYY-MM-DD)·`course`·`professor`. 못 읽으면 물어본다.
   - 덱마다: `key` = 영문 ASCII (이름을 영어로 짧게: 피부종양→tumor, STD→std, 결체조직질환→ctd 처럼. 겹치지 않게), `name` = 수업이름(경로에 못 쓰는 문자 제거, 공백은 `_`), `display` = 수업이름, `period` = pdf 파일명의 `N교시` 부분, `topic` = 수업이름.
   - `pdf`/`pptx` = 오늘 자료 중 파일명에 수업이름이 들어간 것 (오늘 자료 = mp4 와 같은 날짜로 시작하는 파일). `lastyear_note_pdf` = 파일명에 `필기` 와 수업이름이 든 pdf, `lastyear_onepage_pdf` = `한장` 과 수업이름. 없으면 null.
   - `video` = timeline 구간. `audio` = video 앞뒤 10초 (`config.json audio.default_pad_s`), 시작이 0 미만이면 0.
   - `params`·`index_notes` 는 템플릿 기본값.
3. **매칭 표를 보여 주고 AskUserQuestion 으로 확인**받는다 (덱 | key | 오늘 pdf | pptx | 작년 필기 | 작년 한장 | 구간). 틀린 것은 사용자가 말한 대로 고친다.
4. 저장: `<폴더>\lecture.json` (UTF-8, `_주의` 키에 "audio.start 는 전사 후 변경 금지" 문구 포함).

## 3. 자동 구간 실행
`wabel --lecture "<폴더>"` (= audio → slides → pages → transcribe → detect → match → repair → cursor → lastyear → post).
- 전사는 GPU 로 강의 길이의 약 1/3 시간이 걸린다. 백그라운드로 돌리고 로그(`_work\logs\`)를 보며 기다린다.
- 단계가 실패하면 로그의 마지막 30줄과 원인을 보고하고 멈춘다. 고친 뒤 `--from <단계>` 로 이어서.
- `match` 단계 출력의 "확인필요"·"미등장" 페이지와 `repair` 결과(단조=True 인지)를 읽고, 이상하면 `check_skipped.py` 출력으로 판단해 보고한다.
- `lastyear` 커버율이 낮으면(예: 60% 미만) `lastyear_map.py --report` 로 보고서를 만들어 살펴본다.

## 4. notes_<key>.json 작성 (Claude 의 본업)
덱마다 `_work\worksheet_<key>_1_N.txt` 를 읽고 `CLAUDE.md` 의 스키마대로 쓴다. 페이지가 60쪽을 넘으면 `notes_<key>_A.json`, `_B.json` … 으로 나눠 쓰고 `wabel --lecture "<폴더>" merge <key>`.
- 모든 페이지에 최소 `summary` 를 쓴다 (말씀 없이 넘어간 페이지도).
- `fixes`: `⚠저확신`·`+보충` 발화와 의학 용어 오인식을 교정. 타임스탬프는 worksheet 의 것을 그대로.
- `notes`: 작년 필기 형식(용어 → └ 설명). `emphasis`: 보라색(강조)으로 갈 내용만 — 교수님이 시험·중요라고 직접 짚은 강한 강조는 `🔴` 로 시작(글작성 '강조페이지'가 된다). `is_new`: 작년 대응이 "없음(올해 신규)" 인 페이지. `changed`: 작년에도 있었지만 내용이 바뀐 페이지(작년 필기 렌더와 비교해 알게 된 경우).
- `underline`: 글자가 있는 슬라이드마다, 발화에서 읽거나 설명한 글줄을 슬라이드 글자 그대로 나열(하늘색). `emphasis` 에 해당하는 줄은 `{"text": …, "emph": true}`(보라색). 전부 읽으신 페이지는 `"all"`. 사진 슬라이드는 생략. 글자가 슬라이드와 다르면 못 찾으므로 worksheet 의 `<슬라이드>` 글줄에서 복사한다.
- `pointers`: worksheet 의 포인팅 좌표·발화로 무엇을 가리켰는지 라벨.
- `factcheck`: 발언이 교과서와 다르면 근거와 함께.
- `_work\lastyear\<key>\NNN.jpg` (작년 필기 렌더) 는 필요할 때 Read 로 열어 참고한다 (없으면 `wabel … --only pages`).

## 5. 사진 슬라이드 마커 검증
덱마다 `verify_shots.py <key>` → `_work\verify_shots\<key>_pNNN.png` 를 **하나씩 Read 로 보고** 마커가 실제로 가리키는 구조를 확인해 라벨을 교정한다.
결과는 `echo <JSON> | patch_add.py <key>` 로 누적(`{"페이지": {"마커번호": "라벨" | "__DROP__"}}`) → `apply_verify.py <key>`.

## 6. 빌드·검증
`wabel --lecture "<폴더>" build` → `wabel --lecture "<폴더>" verify`. 4번(필기 커버리지)이 실패하면 빠진 페이지의 notes 를 채우고 다시. "못 찾은 밑줄 글자" 가 있으면 그 `underline` 문자열을 슬라이드 글자와 같게 고치고 다시.

## 7. 보고
- `output\index.html` 경로, 덱별 산출물 5종과 태블릿 HTML 크기
- 글작성 초안의 강조·추가·변경 페이지 목록(변경 후보는 확인이 필요하다고 함께)
- 팩트체크 건수, 스크립트 MD 의 "확정하지 못한 구간" 수(타임스탬프 목록)
- 매칭에서 사람이 봐야 할 페이지가 있으면 그것
- 이번에 파이프라인을 손본 게 있으면 한 줄, 다음 강의 개선 제안이 있으면 한 줄
- 마지막에 `_work\verify_shots\`·`pages\`·`lastyear\` 는 지워도 된다고(재생성 가능) 알려 준다. 지우지는 않는다.
