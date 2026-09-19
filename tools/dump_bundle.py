# -*- coding: utf-8 -*-
"""bundle을 Claude가 읽기 좋은 압축 텍스트로 떨군다 (notes 작성용 작업지).
사용법: python dump_bundle.py <deck> [시작페이지] [끝페이지]
출력:  _work/worksheet_<deck>_<a>_<b>.txt
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import common  # noqa: E402


def main():
    lec = common.init()
    deck = sys.argv[1]
    a = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    b = int(sys.argv[3]) if len(sys.argv) > 3 else 9999

    bundle = lec.load_json(lec.bundle(deck))
    lymap = lec.load_json(lec.lastyear_map).get(deck, {}) if lec.lastyear_map.exists() else {}

    L = []
    for p in bundle["pages"]:
        if not (a <= p["page"] <= b):
            continue
        ly = lymap.get(str(p["page"]), [])
        L.append(f"\n{'='*72}\n[p.{p['page']}] {p['t_start']}~{p['t_end']} ({p['seconds']:.0f}s)"
                 f"  작년필기 p{','.join(map(str, ly)) if ly else '없음(올해 신규)'}")
        st = (p["slide_text"] or "").strip()
        if st:
            L.append("<슬라이드>\n" + st)
        else:
            L.append("<슬라이드> (텍스트 없음 — 사진/그림 슬라이드)")
        if p["utterances"]:
            L.append("<발화>")
            for i, u in enumerate(p["utterances"]):
                flag = ""
                if u["lp"] < -0.55:
                    flag = " ⚠저확신"
                if u.get("filled"):
                    flag += " +보충"
                L.append(f"  {i}| [{u['ts']}] {u['text']}{flag}")
        else:
            L.append("<발화> 없음")
        if p["dwells"]:
            L.append("<포인팅>")
            for k, d in enumerate(p["dwells"], 1):
                L.append(f"  {k}| ({d['nx']:.3f},{d['ny']:.3f}) {d['dur']}s @{d['ts']}"
                         f" ← \"{d['said'][:80]}\"")

    txt = "\n".join(L)
    dst = lec.work / f"worksheet_{deck}_{a}_{min(b, bundle['pages'][-1]['page'])}.txt"
    dst.write_text(txt, encoding="utf-8")
    print(f"→ {dst.name}  ({len(txt):,}자)")


if __name__ == "__main__":
    main()
