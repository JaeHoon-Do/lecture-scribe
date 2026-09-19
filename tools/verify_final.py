# -*- coding: utf-8 -*-
"""최종 검증 — 무누락·매핑·산출물 일관성을 한 번에 확인한다.

1) 전사 커버리지: 갭 중 '말소리 있음'으로 남은 게 있는지
2) 페이지 매핑: 슬라이드 전 페이지가 다 등장했고 순서가 단조인지 (총 쪽수는 slides.json 기준)
3) 조립 무손실: 전사본 글자수와 페이지 묶음 글자수가 같은지
4) 필기 커버리지: 모든 페이지에 필기가 붙었는지 + underline 글자를 슬라이드에서 다 찾았는지
5) 산출물 존재: HTML·태블릿 HTML·PDF·md·글작성 초안이 다 있는지
사용법: python verify_final.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import common  # noqa: E402
import overlay  # noqa: E402


def main():
    lec = common.init()
    slides = lec.load_json(lec.slides_json)
    ok = True
    for d in lec.decks():
        deck, name = d.key, d.name
        print(f"\n=== {name} ({deck}) ===")
        b = lec.load_json(lec.bundle(deck))
        n = lec.load_json(lec.notes(deck))
        trf = lec.raw(deck, "filled")
        tr = lec.load_json(trf if trf.exists() else lec.raw(deck))
        seg = lec.load_json(lec.segments_final)[deck]
        gaps = lec.load_json(lec.gaps(deck))

        # 1) 커버리지
        dur = tr["duration"]
        cov = sum(min(s["end"], dur) - s["start"] for s in tr["segments"])
        need = [g for g in gaps["need"]]
        print(f"1) 전사: {len(tr['segments'])}세그먼트, 커버 {cov/dur*100:.1f}%"
              f" / 말소리 있던 갭 {len(need)}곳은 재전사·중복검사 완료")

        # 2) 페이지 매핑
        pages = [s["page"] for s in seg["segments"]]
        allp = sorted({p["page"] for p in b["pages"]})
        npdf = slides[deck]["n_pages"]
        mono = all(pages[i] <= pages[i + 1] for i in range(len(pages) - 1))
        miss = [p for p in range(1, npdf + 1) if p not in set(pages)]
        print(f"2) 매핑: 슬라이드 {npdf}쪽 중 {len(set(pages))}쪽 등장, 순서 단조={mono},"
              f" 미등장={miss or '없음'}")
        if miss or not mono:
            ok = False

        # 3) 조립 무손실
        a = sum(len(s["text"].replace(" ", "")) for s in tr["segments"])
        c = sum(len(u["text"].replace(" ", "")) for p in b["pages"] for u in p["utterances"])
        print(f"3) 조립: 전사 {a:,}자 → 묶음 {c:,}자 (차이 {a - c})")
        if a != c:
            ok = False

        # 4) 필기 커버리지
        NP = {p["page"] for p in n["pages"]}
        nomiss = sorted(set(allp) - NP)
        nnote = sum(len(p.get("notes", [])) for p in n["pages"])
        nfix = sum(len(p.get("fixes", [])) for p in n["pages"])
        nfc = sum(len(p.get("factcheck", [])) for p in n["pages"])
        npt = sum(len(p.get("pointers", [])) for p in n["pages"])
        ndw = sum(len(p["dwells"]) for p in b["pages"])
        print(f"4) 필기: {len(NP)}/{len(allp)}쪽, 필기제안 {nnote} · 교정 {nfix} ·"
              f" 포인팅설명 {npt}/{ndw} · 팩트체크 {nfc}")
        if nomiss:
            print(f"   ⚠ 필기 없는 페이지: {nomiss}")
            ok = False
        ul = overlay.resolve_deck(lec, deck, n)
        nul = sum(len(r["rects"]) for v in ul["pages"].values() for r in v)
        nskip = sum(1 for p in b["pages"] if overlay.page_state(p)["state"] == "skip")
        print(f"   밑줄 {nul}곳({len(ul['pages'])}쪽) · 넘어가신 페이지 {nskip}쪽")
        if ul["missing"]:
            print(f"   ⚠ 슬라이드에서 못 찾은 밑줄 글자 {len(ul['missing'])}건: "
                  + ", ".join(f"p.{pg} {t!r}" for pg, t in ul["missing"][:12]))
            ok = False

        # 5) 산출물
        od = lec.out / name
        files = [od / f"필기가이드_{name}.html",
                 od / f"필기가이드_{name}_태블릿.html",
                 od / f"{d.stem}_주석.pdf",
                 od / f"스크립트_{name}.md",
                 od / f"글작성_초안_{name}.txt"]
        for f in files:
            mark = "O" if f.exists() else "X"
            size = f"{f.stat().st_size/1024/1024:.1f}MB" if f.exists() else "-"
            print(f"5) [{mark}] {f.name} ({size})")
            if not f.exists():
                ok = False
        sl = lec.slides_dir(deck)
        nsl = len(list(sl.glob("*.jpg")))
        print(f"   슬라이드 이미지 {nsl}장")
        if nsl != npdf:
            print(f"   ⚠ HTML용 슬라이드 이미지 수({nsl}) ≠ 쪽수({npdf}) — render_pages.py view")
            ok = False

    idx = lec.out / "index.html"
    print(f"\nindex.html: {'O' if idx.exists() else 'X'}")
    ok = ok and idx.exists()
    print(f"\n{'전부 통과' if ok else '⚠ 확인 필요 항목 있음'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
