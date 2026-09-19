# -*- coding: utf-8 -*-
"""PDF를 페이지 이미지로 렌더링한다 (PyMuPDF).

  match    : 매칭용 저해상(폭 960, 녹화 화면의 슬라이드 영역과 동일 크기) → _work/pages/<deck>/
  view     : 최종 HTML 뷰용 고해상(폭 1400)                              → output/_slides/<deck>/
  lastyear : 작년 필기 PDF(폭 1100) + 작년 한장(폭 1300) — Claude 통독용   → _work/lastyear/<deck>[_onepage]/
크기·품질은 config.json render 항목.

사용법: python render_pages.py [all|match|view|lastyear] [--lecture <폴더>]
"""
import sys
from pathlib import Path

import pymupdf

sys.path.insert(0, str(Path(__file__).parent))
import common  # noqa: E402


def render_page_bytes(doc: pymupdf.Document, index: int, width: int,
                      quality: int = 80) -> bytes:
    """페이지 하나를 폭 width 의 JPEG 바이트로. (태블릿 HTML 내장용으로도 씀)"""
    page = doc[index]
    zoom = width / page.rect.width
    pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
    return pix.tobytes("jpeg", jpg_quality=quality)


def render(pdf: Path, dst: Path, width: int, fmt: str = "png", quality: int = 80):
    dst.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open(str(pdf))
    for i, page in enumerate(doc, 1):
        r = page.rect
        zoom = width / r.width
        pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
        out = dst / f"{i:03d}.{fmt}"
        if fmt == "jpg":
            pix.pil_save(str(out), format="JPEG", quality=quality)
        else:
            pix.save(str(out))
    print(f"  {pdf.name}: {len(doc)}p → {dst} ({pix.width}x{pix.height})")
    doc.close()


def main():
    lec = common.init()
    what = sys.argv[1] if len(sys.argv) > 1 else "all"

    if what in ("all", "match"):
        w, q = common.render_cfg("match")
        print(f"[매칭용 {w}px]")
        for d in lec.decks():
            render(lec.root / d.pdf, lec.pages_dir(d.key), w, "jpg", q)

    if what in ("all", "view"):
        w, q = common.render_cfg("view")
        print(f"[HTML 뷰용 {w}px]")
        for d in lec.decks():
            render(lec.root / d.pdf, lec.slides_dir(d.key), w, "jpg", q)

    if what in ("all", "lastyear"):
        w, q = common.render_cfg("lastyear")
        w2, q2 = common.render_cfg("onepage")
        print(f"[작년 필기 통독용 {w}px / 한장 {w2}px]")
        for d in lec.decks():
            if d.lastyear_note_pdf:
                render(lec.root / d.lastyear_note_pdf, lec.lastyear_dir(d.key), w, "jpg", q)
            if d.lastyear_onepage_pdf:
                render(lec.root / d.lastyear_onepage_pdf,
                       lec.lastyear_dir(d.key, onepage=True), w2, "jpg", q2)


if __name__ == "__main__":
    main()
