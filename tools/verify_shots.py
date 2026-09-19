# -*- coding: utf-8 -*-
"""조직·임상 사진 슬라이드를 마커 얹어 크게 렌더한다 — Claude가 눈으로 검증하기 위한 것.

마커는 속을 비운 링으로 그려 짚은 지점의 픽셀을 가리지 않는다.
번호 라벨은 링 바깥에 붙인다.

출력: _work/verify_shots/<deck>_pNNN.png + <deck>_worksheet.txt
사용법: python verify_shots.py <deck>
"""
import sys
from pathlib import Path

import pymupdf

sys.path.insert(0, str(Path(__file__).parent))
import common  # noqa: E402
from fixes import apply_fixes, said_text  # noqa: E402

PHOTO_MAX_TEXT = 60      # 이보다 글자가 적으면 사진 위주 슬라이드로 본다


def main(deck):
    lec = common.current()
    _, FONT_B = common.fonts()
    ZOOM = float(common.cfg()["render"].get("verify_zoom", 2.4))
    SHOTS = lec.shots_dir
    SHOTS.mkdir(exist_ok=True)
    src = pymupdf.open(str(lec.deck_pdf(deck)))
    B = {p["page"]: p for p in lec.load_json(lec.bundle(deck))["pages"]}
    nf = lec.notes(deck)
    N = {p["page"]: p for p in (lec.load_json(nf)["pages"] if nf.exists() else [])}

    ws = []
    done = []
    for i in range(src.page_count):
        pg = i + 1
        b = B.get(pg)
        if not b or not b.get("dwells"):
            continue
        if len(src[i].get_text().strip()) >= PHOTO_MAX_TEXT:
            continue

        out = pymupdf.open()
        r = src[i].rect
        page = out.new_page(width=r.width, height=r.height)
        page.show_pdf_page(r, src, i)
        page.insert_font(fontname="KoB", fontfile=FONT_B)
        font = pymupdf.Font(fontfile=FONT_B)
        for k, d in enumerate(b["dwells"], 1):
            x, y = d["nx"] * r.width, d["ny"] * r.height
            page.draw_circle((x, y), 9.0, color=(0.92, 0.1, 0.1), width=1.8)
            page.draw_circle((x, y), 1.2, color=(0.92, 0.1, 0.1),
                             fill=(0.92, 0.1, 0.1), width=0.5)
            lx, ly = x + 10.0, y - 8.0
            s = str(k)
            tw = font.text_length(s, 9)
            page.draw_rect(pymupdf.Rect(lx - 1.5, ly - 8.5, lx + tw + 1.5, ly + 1.5),
                           color=None, fill=(1, 1, 1), fill_opacity=0.85)
            page.insert_text((lx, ly), s, fontname="KoB", fontsize=9,
                             color=(0.92, 0.1, 0.1))
        png = SHOTS / f"{deck}_p{pg:03d}.png"
        page.get_pixmap(matrix=pymupdf.Matrix(ZOOM, ZOOM)).save(png)
        out.close()
        done.append(pg)

        n = N.get(pg, {})
        fixed = apply_fixes(b["utterances"], n.get("fixes"), n.get("drops"))
        labs = {p.get("n"): p.get("label", "") for p in n.get("pointers", [])}
        ws.append(f"\n{'='*70}\n[{deck} p.{pg}]  {b['t_start']}–{b['t_end']}"
                  f"  ({b['seconds']:.0f}초)")
        if n.get("summary"):
            ws.append(f"요지: {n['summary']}")
        for k, d in enumerate(b["dwells"], 1):
            said = (said_text(d, fixed) or "").strip()
            ws.append(f"  ({k}) nx={d['nx']:.3f} ny={d['ny']:.3f} "
                      f"{d['dur']:.1f}초  현재라벨: {labs.get(k) or '(없음)'}")
            if said:
                ws.append(f"       말씀: {said[:200]}")
        ws.append("  -- 그 페이지 발화 전문 --")
        for u in fixed:
            ws.append(f"   [{u['ts']}] {u['fixed']}")

    (SHOTS / f"{deck}_worksheet.txt").write_text("\n".join(ws), encoding="utf-8")
    print(f"{deck}: {len(done)}쪽 -> {done}")


if __name__ == "__main__":
    common.init()
    main(sys.argv[1])
