# -*- coding: utf-8 -*-
"""전사본 + 슬라이드 페이지 구간 + 마우스 dwell을 '페이지별 묶음'으로 합친다.

- 전사 세그먼트가 페이지 경계를 걸치면 단어 타임스탬프로 잘라 양쪽에 나눠 담는다
  (그래야 어떤 말이 어느 슬라이드에서 나왔는지 어긋나지 않는다)
- 같은 페이지가 여러 구간으로 나뉘어 있으면(빌드 애니메이션 등) 하나로 합친다
- dwell에는 그 시점에 하던 말(±2.5초)을 붙여 둔다 → "여기 보세요"가 어디를 가리켰는지

사용법: python assemble.py <키>
출력:  _work/bundle_<키>.json
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import common  # noqa: E402
from common import hms as hhmmss  # noqa: E402


def main():
    lec = common.init()
    key = sys.argv[1]
    segs_f = lec.raw(key, "filled")
    tr = lec.load_json(segs_f if segs_f.exists() else lec.raw(key))
    off = tr["offset"]
    pages_src = lec.load_json(lec.segments_final)[key]["segments"]
    cur = lec.load_json(lec.cursor(key))[key]
    slides = lec.load_json(lec.slides_json)[key]

    # 페이지별 표시 구간(절대 영상 시각) 목록
    win = {}
    for s in pages_src:
        win.setdefault(s["page"], []).append((float(s["start"]), float(s["end"])))
    for p in win:
        win[p].sort()

    def page_at(t: float):
        for s in pages_src:
            if s["start"] <= t < s["end"]:
                return s["page"]
        return pages_src[-1]["page"] if t >= pages_src[-1]["end"] else pages_src[0]["page"]

    # 경계 시각들
    bounds = sorted({float(s["start"]) for s in pages_src}
                    | {float(s["end"]) for s in pages_src})

    # 전사 세그먼트를 페이지로 배분 (경계를 걸치면 단어 단위로 분할)
    perpage = {}
    for s in tr["segments"]:
        a, b = s["abs_start"], s["abs_end"]
        cuts = [c for c in bounds if a < c < b]
        pieces = []
        if not cuts or not s.get("words"):
            pieces = [(a, b, s["text"])]
        else:
            edges = [a] + cuts + [b]
            for i in range(len(edges) - 1):
                lo, hi = edges[i], edges[i + 1]
                ws = [w["w"] for w in s["words"]
                      if lo <= (w["s"] + w["e"]) / 2 + off < hi]
                txt = "".join(ws).strip()
                if txt:
                    pieces.append((lo, hi, txt))
            if not pieces:
                pieces = [(a, b, s["text"])]
        for lo, hi, txt in pieces:
            p = page_at((lo + hi) / 2)
            perpage.setdefault(p, []).append({
                "t": round(lo, 2), "te": round(hi, 2), "ts": hhmmss(lo),
                "text": txt,
                "lp": s["avg_logprob"], "nsp": s["no_speech_prob"],
                "filled": bool(s.get("filled")),
                "split": len(pieces) > 1,
            })

    # dwell을 페이지로 모은다. 가까운 자리에서 반복해 머문 것은 하나로 합치고
    # (마커가 겹쳐 읽기 어려워짐), 그 시점에 한 말은 '가장 많이 겹치는 발화' 하나만 붙인다.
    raw = {}
    for r in cur["segments"]:
        for d in r["dwells"]:
            e = dict(d)
            e["seg"] = r["seg"]
            raw.setdefault(r["page"], []).append(e)

    NEAR = 0.045          # 같은 지점으로 볼 정규화 거리
    dwell = {}
    for p, lst in raw.items():
        lst.sort(key=lambda x: x["t0"])
        merged = []
        for d in lst:
            hit = None
            for m in merged:
                if (abs(m["nx"] - d["nx"]) < NEAR and abs(m["ny"] - d["ny"]) < NEAR
                        and d["t0"] - m["t1"] < 12):
                    hit = m
                    break
            if hit:
                w1, w2 = hit["dur"], d["dur"]
                tot = max(w1 + w2, 0.01)
                hit["nx"] = round((hit["nx"] * w1 + d["nx"] * w2) / tot, 4)
                hit["ny"] = round((hit["ny"] * w1 + d["ny"] * w2) / tot, 4)
                hit["x"] = round((hit["x"] * w1 + d["x"] * w2) / tot, 1)
                hit["y"] = round((hit["y"] * w1 + d["y"] * w2) / tot, 1)
                hit["t1"] = max(hit["t1"], d["t1"])
                hit["dur"] = round(hit["dur"] + d["dur"], 2)
                hit["n_merge"] = hit.get("n_merge", 1) + 1
            else:
                merged.append(dict(d))

        merged = [m for m in merged if m["dur"] >= 1.0]
        merged.sort(key=lambda x: -x["dur"])
        merged = merged[:10]                      # 페이지당 마커 상한
        merged.sort(key=lambda x: x["t0"])

        ulist = perpage.get(p, [])
        for m in merged:
            m["ts"] = hhmmss(m["t0"])
            best, bs = None, 0.0
            for u in ulist:
                ov = min(u["te"], m["t1"] + 1.5) - max(u["t"], m["t0"] - 1.5)
                if ov > bs:
                    best, bs = u, ov
            m["said"] = best["text"] if best else ""
            m["said_ts"] = best["ts"] if best else ""
        dwell[p] = merged

    stext = {x["page"]: x["text"] for x in slides["pages"]}
    out = []
    for p in sorted(set(list(win.keys()) + list(perpage.keys()))):
        utt = sorted(perpage.get(p, []), key=lambda x: x["t"])
        spans = win.get(p, [])
        out.append({
            "page": p,
            "spans": [[round(a, 2), round(b, 2)] for a, b in spans],
            "t_start": hhmmss(spans[0][0]) if spans else "",
            "t_end": hhmmss(spans[-1][1]) if spans else "",
            "seconds": round(sum(b - a for a, b in spans), 1),
            "slide_text": stext.get(p, ""),
            "utterances": utt,
            "chars": sum(len(u["text"]) for u in utt),
            "dwells": dwell.get(p, []),
        })

    res = {"key": key, "offset": off, "n_pages": len(out),
           "bbox": cur["bbox"], "pages": out}
    lec.save_json(lec.bundle(key), res)

    empty = [o["page"] for o in out if not o["utterances"]]
    total = sum(o["chars"] for o in out)
    print(f"{key}: {len(out)}페이지, 발화 {sum(len(o['utterances']) for o in out)}건 "
          f"({total:,}자), dwell {sum(len(o['dwells']) for o in out)}개")
    if empty:
        print(f"  발화 없는 페이지: {empty}")
    print(f"→ bundle_{key}.json")


if __name__ == "__main__":
    main()
