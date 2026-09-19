---
name: 재빌드
description: notes_<key>.json 을 손으로 고친 뒤 산출물(HTML·태블릿 HTML·PDF·MD·index)만 다시 만들고 검증한다. "/재빌드 [폴더이름]" 또는 "산출물만 다시 만들어" 라고 할 때. (글작성 초안도 같이 다시 만들어진다)
---

# /재빌드 [폴더이름]

1. 강의 폴더 확정: 인자가 있으면 `<repo>\<인자>`, 없으면 `lecture.json` 이 있는 폴더가 하나뿐일 때 그것, 아니면 물어본다.
2. `_work\bundle_<key>.json` 과 `_work\notes_<key>.json` 이 덱마다 있는지 확인. 없으면 `/필기` 가 먼저라고 알린다.
   `notes_<key>_A/B….json` 조각이 최종본보다 새로우면 `wabel --lecture "<폴더>" merge <key>` 를 먼저 (거부되면 이유를 보여 주고 `--force` 는 사용자 확인 후).
3. `"<repo>\wabel.cmd" --lecture "<폴더>" build` → `… verify`.
4. 실패한 항목이 있으면 원인과 함께 보고(밑줄 글자를 못 찾은 경우는 그 문자열을 슬라이드 글자대로 고쳐 다시). 통과하면 `output\index.html` 경로와 바뀐 파일 크기를 짧게 보고.
