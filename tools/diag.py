# -*- coding: utf-8 -*-
"""작은 진단 도구 모음 (예전 _empty_pages / _review_recheck / _verify_assemble / _peek_pdf).

사용법:
  python diag.py empty                      덱별 '텍스트 없는 페이지'(사진 슬라이드) 목록 + 작년 대응
  python diag.py recheck <key>              갭 보충분과 재확인 불일치 건을 읽기 좋게 출력
  python diag.py assemble [key]             조립 단계에서 글자가 새지 않았는지 확인
  python diag.py peek <pdf경로> <페이지…>    만든 주석 PDF의 페이지를 png로 → _work/verify/
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import common  # noqa: E402


def cmd_empty(lec):
    sl = lec.load_json(lec.slides_json)
    lm = lec.load_json(lec.lastyear_map) if lec.lastyear_map.exists() else {}
    for deck, d in sl.items():
        empty = [p["page"] for p in d["pages"] if not p["text"].strip()]
        ly = [",".join(map(str, lm.get(deck, {}).get(str(p), []))) or "-" for p in empty]
        print(f"[{deck}] 사진 슬라이드 {len(empty)}/{d['n_pages']}쪽")
        print("  올해:", empty)
        print("  작년:", ly)


def cmd_recheck(lec, key):
    tr = lec.load_json(lec.raw(key, "filled"))
    ts = common.hms
    print(f"=== [{key}] 갭에서 새로 보충된 발화 ===")
    for s in tr["segments"]:
        if s.get("filled"):
            print(f"[{ts(s['abs_start'])}] {s['text']}")
    f = lec.recheck(key)
    if f.exists():
        rc = lec.load_json(f)
        dis = [r for r in rc if not r["agree"]]
        print(f"\n=== [{key}] 조건별로 결과가 갈린 구간 {len(dis)}건 ===")
        for r in dis:
            print(f"\n[{ts(r['abs'])}] p{r['page']} lp={r['lp']}")
            print(f"  1차: {r['v1']}")
            print(f"  2차: {r['v2']}")
            print(f"  3차(슬라이드 힌트): {r['v3']}")


def cmd_assemble(lec, key):
    f = lec.raw(key, "filled")
    if not f.exists():
        f = lec.raw(key)
    tr = lec.load_json(f)
    b = lec.load_json(lec.bundle(key))
    a = sum(len(s["text"].replace(" ", "")) for s in tr["segments"])
    c = sum(len(u["text"].replace(" ", "")) for p in b["pages"] for u in p["utterances"])
    print(f"[{key}] 원본 전사 {a:,}자 / 조립 후 {c:,}자 (공백 제외, 차이 {a-c})")
    print(f"  세그먼트 {len(tr['segments'])}개 → 발화 {sum(len(p['utterances']) for p in b['pages'])}건")
    for p in [p for p in b["pages"] if not p["utterances"]]:
        print(f"  발화 없음 p{p['page']}: 표시 {p['seconds']}s spans={p['spans']}")
    for p in sorted(b["pages"], key=lambda p: -p["chars"])[:2]:
        print(f"\n--- p{p['page']} ({p['t_start']}~{p['t_end']}, {p['seconds']}s, {p['chars']}자) ---")
        for u in p["utterances"][:6]:
            print(f"  [{u['ts']}] {u['text']}")


def cmd_peek(lec, pdf, pages):
    import pymupdf
    zoom = float(common.cfg()["render"].get("peek_zoom", 1.5))
    out = lec.verify_dir
    out.mkdir(exist_ok=True)
    pdf = Path(pdf)
    doc = pymupdf.open(str(pdf))
    for a in pages:
        i = int(a) - 1
        pix = doc[i].get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
        f = out / f"pdf_{pdf.stem[:12]}_{i+1:03d}.png"
        pix.save(str(f))
        print("→", f)


def main():
    lec = common.init()
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    what, rest = sys.argv[1], sys.argv[2:]
    if what == "empty":
        cmd_empty(lec)
    elif what == "recheck":
        cmd_recheck(lec, rest[0])
    elif what == "assemble":
        cmd_assemble(lec, rest[0] if rest else lec.keys()[0])
    elif what == "peek":
        cmd_peek(lec, rest[0], rest[1:])
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
