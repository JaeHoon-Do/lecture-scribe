# -*- coding: utf-8 -*-
"""나눠 쓴 notes_<deck>_A/B/C.json을 하나의 notes_<deck>.json으로 합친다.
페이지 번호 기준으로 정렬하고, 중복·누락 페이지를 보고한다.

주의: 최종 notes_<deck>.json 이 조각들보다 새로우면(apply_verify 등으로 손본 뒤)
      --force 없이는 덮어쓰지 않는다. 그 검증 반영분이 사라지기 때문.
사용법: python merge_notes.py <deck> [--force]
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import common  # noqa: E402


def main():
    lec = common.init()
    deck = sys.argv[1]
    force = "--force" in sys.argv
    W = lec.work

    parts = sorted(W.glob(f"notes_{deck}_*.json"))
    if not parts:
        sys.exit(f"조각 파일이 없습니다: notes_{deck}_*.json")

    final = lec.notes(deck)
    if final.exists() and not force:
        newest_part = max(p.stat().st_mtime for p in parts)
        if final.stat().st_mtime > newest_part:
            sys.exit(f"⚠ {final.name} 이 조각들보다 새롭습니다(검증 반영분일 수 있음). "
                     f"정말 덮어쓰려면 --force")

    pages, seen, title = [], {}, None
    for f in parts:
        d = json.loads(f.read_text(encoding="utf-8"))
        title = d.get("title") or title
        for p in d["pages"]:
            n = p["page"]
            if n in seen:
                print(f"  ⚠ 중복 페이지 p{n} ({f.name}) — 뒤엣것으로 덮어씀")
            seen[n] = p
        print(f"  {f.name}: {len(d['pages'])}쪽")

    pages = [seen[k] for k in sorted(seen)]
    bundle = lec.load_json(lec.bundle(deck))
    allp = {p["page"] for p in bundle["pages"]}
    missing = sorted(allp - set(seen))
    extra = sorted(set(seen) - allp)

    out = {"deck": deck, "title": title or deck, "pages": pages}
    lec.save_json(final, out)

    nf = sum(len(p.get("factcheck", [])) for p in pages)
    nn = sum(len(p.get("notes", [])) for p in pages)
    nx = sum(len(p.get("fixes", [])) for p in pages)
    print(f"→ notes_{deck}.json : {len(pages)}쪽 / 필기 {nn}개 / 교정 {nx}개 / 팩트체크 {nf}건")
    if missing:
        print(f"  ⚠ 필기가 없는 페이지: {missing}")
    if extra:
        print(f"  ⚠ 자료에 없는 페이지 번호: {extra}")


if __name__ == "__main__":
    main()
