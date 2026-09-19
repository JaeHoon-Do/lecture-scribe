# -*- coding: utf-8 -*-
"""공유용 글작성.txt 초안을 만든다 (수업별).

사용자가 필기·한장·야마를 올릴 때 함께 적는 글의 뼈대. 형식은 사용자의 기존 글작성.txt 를 따른다:
  0. 후기 / 1. 필기(강조페이지·추가페이지·변경페이지) / 2. 한장 / 3. 야마
숫자 목록은 notes 와 작년 대응에서 뽑고, 후기·야마처럼 사람이 써야 하는 칸은 비워 둔다.
맨 아래 '초안 근거' 에 무엇을 보고 골랐는지 남겨서 사용자가 확인·수정하기 쉽게 한다.

  강조페이지 = notes.emphasis 가 🔴 로 시작하는 페이지 (교수님이 직접 '중요·시험' 식으로 짚은 강한 강조)
             (🔴 없는 emphasis 는 '그 외 강조 언급' 으로 따로 적는다)
  추가페이지 = notes.is_new 이거나 lastyear_map 에 작년 대응이 없는 페이지
  변경페이지 = notes.changed 인 페이지. 그 아래 '변경 후보' = 작년 대응은 있지만 이미지 유사도가
             그 덱의 중앙값보다 크게 낮은 페이지 (lastyear_scores.json, 자동이라 확인 필요)
  넘어가신 페이지 = 말씀 없이 지나간 페이지 (overlay.page_state)

사용법: python make_writeup.py <deck>
출력:  output/<수업이름>/글작성_초안_<수업이름>.txt
"""
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import common  # noqa: E402
import overlay  # noqa: E402

CHANGE_DROP = 0.20     # 중앙값보다 이만큼 낮으면 "변경 후보" (손글씨가 많은 쪽도 낮아지므로 확인용)
CHANGE_MAX = 6         # 후보는 유사도 낮은 순으로 이만큼만


def _fmt(pages):
    return ", ".join(str(p) for p in sorted(set(pages))) if pages else "없음"


def main():
    lec = common.init()
    deck = sys.argv[1]
    d = lec.deck(deck)
    bundle = lec.load_json(lec.bundle(deck))
    nf = lec.notes(deck)
    notes = lec.load_json(nf) if nf.exists() else {"pages": []}
    N = {p["page"]: p for p in notes.get("pages", [])}
    lymap = lec.load_json(lec.lastyear_map).get(deck, {}) if lec.lastyear_map.exists() else {}
    sf = lec.work / "lastyear_scores.json"
    scores = lec.load_json(sf).get(deck, {}) if sf.exists() else {}
    has_lastyear = bool(d.lastyear_note_pdf) and bool(lymap)

    strong, weak, new, changed, skipped = [], [], [], [], []
    for p in bundle["pages"]:
        pg = p["page"]
        n = N.get(pg, {})
        e = (n.get("emphasis") or "").strip()
        if e.startswith("🔴"):
            strong.append(pg)
        elif e:
            weak.append(pg)
        if n.get("is_new") or (has_lastyear and not lymap.get(str(pg))):
            new.append(pg)
        if n.get("changed"):
            changed.append(pg)
        if overlay.page_state(p)["state"] == "skip":
            skipped.append(pg)

    # 변경 후보 — 작년 대응이 있는데 유사도가 유난히 낮은 페이지
    cand = []
    if scores:
        vals = [v for k, v in scores.items() if int(k) not in new]
        med = statistics.median(vals) if vals else 0
        for k, v in scores.items():
            pg = int(k)
            if pg not in new and pg not in changed and v < med - CHANGE_DROP:
                cand.append((pg, v))
        cand = sorted(sorted(cand, key=lambda x: x[1])[:CHANGE_MAX])

    ly_note = ""
    if not d.lastyear_note_pdf:
        ly_note = "(작년 필기 pdf 가 없어 추가·변경페이지는 판단하지 않았습니다)"
        new = []

    L = [f"# {lec.date} {d.period} {lec.professor} · {d.display} — 글작성 초안",
         "# 숫자 목록은 자동으로 뽑은 것입니다. 후기·한장·야마 칸은 직접 채우세요.",
         "# 맨 아래 '초안 근거' 는 올릴 때 지우면 됩니다.",
         "",
         "0. 후기",
         "<사진>",
         "",
         "",
         "1. 필기",
         "<파일>",
         f"강조페이지: {_fmt(strong)}",
         f"추가페이지: {_fmt(new)}" + (f"  {ly_note}" if ly_note else ""),
         f"변경페이지: {_fmt(changed)}",
         "",
         "2. 한장",
         "<파일>",
         "보라색으로 올해 강조점을 표시하였습니다.",
         "",
         "3. 야마",
         "<파일>",
         "",
         "",
         "─" * 40,
         "초안 근거 (올릴 때 지우세요)",
         f"· 강조페이지 = notes 의 🔴 강조 {len(strong)}쪽. 그 외 강조 언급: {_fmt(weak)}",
         f"· 추가페이지 = 작년 필기에 대응 없는 페이지(is_new / lastyear_map)."
         + (f" 작년 {Path(d.lastyear_note_pdf).name}" if d.lastyear_note_pdf else ""),
         f"· 변경페이지 = notes.changed. 자동 변경 후보(작년과 이미지 유사도 낮은 순 최대 {CHANGE_MAX}개 — "
         f"손글씨가 많은 페이지도 잡히므로 확인 필요): "
         + (", ".join(f"{pg}({v:.2f})" for pg, v in cand) if cand
            else ("없음" if scores else "유사도 파일 없음 — wabel --only lastyear 로 생성")),
         f"· 말씀 없이 넘어가신 페이지 (초록 '넘어가셨습니다'): {_fmt(skipped)}",
         f"· 팩트체크 있는 페이지: {_fmt([pg for pg, n in N.items() if n.get('factcheck')])}",
         ""]

    dst = lec.outdir(deck) / f"글작성_초안_{lec.title(deck)}.txt"
    dst.write_text("\n".join(L), encoding="utf-8")
    print(f"→ {dst}  (강조 {len(strong)} · 추가 {len(new)} · 변경 {len(changed)}"
          f"+후보 {len(cand)} · 넘어감 {len(skipped)})")


if __name__ == "__main__":
    main()
