# -*- coding: utf-8 -*-
"""슬라이드 위에 얹는 표시 — 밑줄(읽은 곳·강조)과 '넘어가셨습니다' 도장.
HTML(make_html)·PDF(make_pdf)·index·글작성 초안이 같은 판정을 쓰도록 한 곳에 모았다.

사용자 손필기 관례 (와벨 색원칙):
  하늘색 밑줄 = 교수님이 읽으신/설명하신 부분 전부
  보라색 밑줄 = 강조
  초록 글씨 '넘어가셨습니다' = 수업하지 않고 지나간 슬라이드

notes_<key>.json  pages[].underline 항목 형식 (섞어 써도 된다):
  "Treponema pallidum"                     → 그 글자를 찾아 하늘색 밑줄
  {"text": "Sexual exposure", "emph": true} → 보라색(강조)
  {"text": "Routes", "nth": 2}              → 같은 글자가 여러 번이면 몇 번째(1부터). 없으면 전부
  {"rect": [x0, y0, x1, y1], "emph": false} → 글자가 없는 슬라이드(사진·표 이미지)에서 0~1 정규화 좌표로 직접
  "all"                                    → 페이지의 글줄 전부 하늘색 (전부 읽으신 페이지). 보라 항목과 겹치는 줄은 뺀다
글자 찾기는 PyMuPDF search_for (대소문자 무시). 못 찾으면 산출물에 ⚠ 로 남고 verify_final 이 걸러 낸다.
"""

# 색 (0~1 RGB) — 손필기 색과 비슷하게
CYAN = (0.40, 0.83, 0.93)
PURPLE = (0.62, 0.36, 0.86)
GREEN = (0.09, 0.64, 0.29)
CYAN_CSS = "rgba(102,212,238,.82)"
PURPLE_CSS = "rgba(158,92,219,.82)"
GREEN_CSS = "#16a34a"

SKIP_CHARS = 6        # 발화 글자수(공백 제외)가 이보다 적으면("이렇게"·"두고" 수준) '말씀 없이 넘어감'으로 본다
FAST_SECONDS = 5.0    # 이보다 짧게 떠 있으면 '빠르게 지나감'


def page_state(bp: dict) -> dict:
    """bundle 페이지 → {"state": "skip"|"fast"|None, "label": 표시 문구, "seconds": n}
    skip = 말씀 없이 넘어감 (초록 도장) / fast = 말은 했지만 5초 미만 (배지만)."""
    sec = float(bp.get("seconds") or 0)
    chars = sum(len(u["text"].replace(" ", "")) for u in bp.get("utterances", []))
    if chars < SKIP_CHARS:
        return {"state": "skip", "seconds": sec,
                "label": f"넘어가셨습니다 ({sec:.0f}초)" if sec else "넘어가셨습니다"}
    if sec < FAST_SECONDS:
        return {"state": "fast", "seconds": sec, "label": f"빠르게 지나감 ({sec:.0f}초)"}
    return {"state": None, "seconds": sec, "label": ""}


def _norm(rect, page_rect):
    W, H = page_rect.width, page_rect.height
    return [round(rect.x0 / W, 4), round(rect.y0 / H, 4),
            round(rect.x1 / W, 4), round(rect.y1 / H, 4)]


def _line_rects(page):
    """페이지의 글줄 bbox 목록 (빈 줄 제외)."""
    out = []
    for b in page.get_text("dict").get("blocks", []):
        for ln in b.get("lines", []):
            t = "".join(s["text"] for s in ln["spans"]).strip()
            if t:
                out.append((t, ln["bbox"]))
    return out


def resolve_underlines(page, items) -> list:
    """notes 의 underline 항목들을 정규화 좌표로 바꾼다.
    page = pymupdf.Page (원본 슬라이드). 반환: [{"kind": "read"|"emph", "text": …, "rects": [[x0,y0,x1,y1],…], "ok": bool}]
    ok=False 는 글자를 못 찾은 항목(rects 비어 있음)."""
    import pymupdf
    out = []
    if not items:
        return out
    if isinstance(items, str):
        items = [items]
    pr = page.rect
    items = [{"text": it} if isinstance(it, str) else dict(it) for it in items]
    # "all" 은 보라(강조) 항목이 정해진 뒤에 처리해야 겹치는 줄을 뺄 수 있다
    items.sort(key=lambda it: str(it.get("text", "")).strip().lower() == "all")
    for it in items:
        kind = "emph" if it.get("emph") else "read"
        if str(it.get("text", "")).strip().lower() == "all":
            emph_rects = [rc for o in out if o["kind"] == "emph" for rc in o["rects"]]
            rects = []
            for _, bb in _line_rects(page):
                r = _norm(pymupdf.Rect(bb), pr)
                cy = (r[1] + r[3]) / 2
                if any(e[1] <= cy <= e[3] and e[0] < r[2] and e[2] > r[0] for e in emph_rects):
                    continue
                rects.append(r)
            out.append({"kind": kind, "text": "all", "rects": rects, "ok": bool(rects)})
            continue
        if "rect" in it:
            r = [float(v) for v in it["rect"]]
            out.append({"kind": kind, "text": it.get("label", "(직접 지정)"),
                        "rects": [r], "ok": len(r) == 4})
            continue
        q = str(it.get("text", "")).strip()
        if not q:
            continue
        hits = page.search_for(q)
        if not hits:
            # 따옴표·하이픈 차이나 줄바꿈 때문에 못 찾는 경우 — 공백을 줄여서 한 번 더
            q2 = " ".join(q.split())
            hits = page.search_for(q2) if q2 != q else []
        nth = it.get("nth")
        if nth and hits:
            # search_for 는 한 구절이 줄바꿈으로 두 사각형이 될 수 있어 y 로 묶어 n 번째 '출현'을 고른다
            groups = []
            for h in hits:
                if groups and abs(groups[-1][-1].y0 - h.y0) < h.height * 1.5 and h.x0 >= groups[-1][-1].x1 - 2:
                    groups[-1].append(h)
                else:
                    groups.append([h])
            hits = groups[nth - 1] if 1 <= nth <= len(groups) else []
        out.append({"kind": kind, "text": q, "rects": [_norm(h, pr) for h in hits],
                    "ok": bool(hits)})
    return out


def underline_geometry(r):
    """정규화 글자 bbox → 밑줄 사각형(정규화). 글자 아래쪽에 굵은 선이 걸치게."""
    x0, y0, x1, y1 = r
    h = y1 - y0
    t = min(max(h * 0.16, 0.006), 0.014)
    return [x0 - 0.002, y1 - t * 0.55, x1 + 0.004, y1 + t * 0.45]


def resolve_deck(lec, deck, notes) -> dict:
    """덱 전체: {page: [항목…]} + 못 찾은 목록. PDF 는 한 번만 연다."""
    import pymupdf
    doc = pymupdf.open(str(lec.deck_pdf(deck)))
    res, missing = {}, []
    for p in notes.get("pages", []):
        items = p.get("underline")
        if not items:
            continue
        pg = p["page"]
        if not (1 <= pg <= len(doc)):
            missing.append((pg, "(페이지 범위 밖)"))
            continue
        r = resolve_underlines(doc[pg - 1], items)
        res[pg] = r
        missing += [(pg, x["text"]) for x in r if not x["ok"]]
    doc.close()
    return {"pages": res, "missing": missing}
