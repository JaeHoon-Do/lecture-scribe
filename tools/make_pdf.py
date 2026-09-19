# -*- coding: utf-8 -*-
"""오늘 수업 자료 PDF에 스크립트·포인팅을 얹은 '주석본'을 만든다 (PyMuPDF).

레이아웃: 원본 슬라이드를 왼쪽에 그대로 놓고, 오른쪽에 폭을 넓혀 만든 여백 단에
          ① 이 슬라이드 요지 ② 교수님 강조 ③ 필기 제안 ④ 팩트체크
          ⑤ 교수님이 짚은 곳(번호별) ⑥ 말씀 전문(타임스탬프)
          을 세로로 흘려 넣는다. 슬라이드를 가리지 않으면서 옆에서 바로 읽힌다.
          슬라이드 위에는 교수님이 마우스로 머문 지점에 번호 원을 그리고,
          notes 의 underline(읽으신 곳 = 하늘색, 강조 = 보라색)을 밑줄로, 말씀 없이 넘어간
          페이지에는 초록 '넘어가셨습니다' 도장을 찍는다 (손필기 색 규칙과 동일).
          한 페이지에 다 안 들어가면 '이어짐' 페이지를 추가한다.

입력: 원본 PDF + _work/bundle_<deck>.json + _work/notes_<deck>.json
출력: output/<수업이름>/<원본이름>_주석.pdf
사용법: python make_pdf.py <deck>
폰트: config.json fonts (맑은 고딕 — ①②③ 원문자 포함)
"""
import sys
from pathlib import Path

import pymupdf

sys.path.insert(0, str(Path(__file__).parent))
import common  # noqa: E402
from fixes import apply_fixes, circled, clean_emph, dwell_marks, said_text  # noqa: E402
import overlay  # noqa: E402

FN_R, FN_B = "KoR", "KoB"
FONT_R = FONT_B = None     # main()에서 config로 채움

COLW_RATIO = 0.66      # 오른쪽 단 폭 = 슬라이드 폭 * 이 비율
PAD = 16
FS = 8.4               # 본문 글자 크기
LH = 1.42              # 줄간격 배수

C_INK = (0.11, 0.12, 0.14)
C_DIM = (0.42, 0.45, 0.50)
C_BLUE = (0.11, 0.31, 0.85)
C_RED = (0.75, 0.15, 0.15)
C_AMBER = (0.63, 0.38, 0.03)
C_GREEN = (0.06, 0.46, 0.43)
C_LINE = (0.87, 0.89, 0.91)


class Flow:
    """오른쪽 단에 블록을 순서대로 흘려 넣고, 넘치면 이어짐 페이지를 만든다."""

    def __init__(self, doc, slide_rect, colx, coly, colw, colh, mkpage):
        self.doc = doc
        self.slide_rect = slide_rect
        self.colx, self.coly0, self.colw, self.colh = colx, coly, colw, colh
        self.mkpage = mkpage           # () -> 새 이어짐 페이지
        self.page = None
        self.y = 0.0

    def start(self, page):
        self.page = page
        self.y = self.coly0

    def _need(self, h):
        if self.y + h <= self.coly0 + self.colh:
            return
        self.page = self.mkpage()
        self.y = self.coly0

    def rule(self, gap=5):
        self._need(gap + 2)
        self.page.draw_line((self.colx, self.y + gap / 2),
                            (self.colx + self.colw, self.y + gap / 2),
                            color=C_LINE, width=0.6)
        self.y += gap + 2

    def head(self, text, color=C_INK):
        self._need(15)
        self.page.insert_text((self.colx, self.y + 8), text, fontname=FN_B,
                              fontsize=8.6, color=color)
        self.y += 13

    def para(self, text, indent=0.0, color=C_INK, fs=FS, bold=False, gap=3.0,
             bar=None, pfx=None, pfx_color=C_RED):
        """pfx = 첫 줄 왼쪽 여백에 따로 찍는 표식(교수님이 짚고 있던 마커 번호).
        본문과 색을 달리 하려고 텍스트에 섞지 않고 별도로 그린다. 호출부가
        indent에 표식 폭만큼을 이미 얹어 준다(내어쓰기)."""
        if not text:
            return
        fn = FN_B if bold else FN_R
        w = self.colw - indent
        font = pymupdf.Font(fontfile=FONT_B if bold else FONT_R)
        lines = self._wrap(text, font, fs, w)
        h = len(lines) * fs * LH
        # 한 덩어리가 아예 안 들어가면 페이지를 넘겨서 시작
        if self.y + min(h, fs * LH * 3) > self.coly0 + self.colh:
            self.page = self.mkpage()
            self.y = self.coly0
        for j, ln in enumerate(lines):
            self._need(fs * LH)
            if bar:
                self.page.draw_line((self.colx + indent - 5, self.y),
                                    (self.colx + indent - 5, self.y + fs * LH),
                                    color=bar, width=2.0)
            if j == 0 and pfx:
                pw = pymupdf.Font(fontfile=FONT_B).text_length(pfx, fs)
                self.page.insert_text(
                    (self.colx + indent - pw - 2.0, self.y + fs * 0.95), pfx,
                    fontname=FN_B, fontsize=fs, color=pfx_color)
            self.page.insert_text((self.colx + indent, self.y + fs * 0.95), ln,
                                  fontname=fn, fontsize=fs, color=color)
            self.y += fs * LH
        self.y += gap

    @staticmethod
    def _wrap(text, font, fs, w):
        out = []
        for raw in str(text).split("\n"):
            cur = ""
            for ch in raw:
                if font.text_length(cur + ch, fs) > w and cur:
                    out.append(cur)
                    cur = ch.lstrip() if ch == " " else ch
                else:
                    cur += ch
            out.append(cur)
        return out or [""]


def main():
    global FONT_R, FONT_B
    lec = common.init()
    FONT_R, FONT_B = common.fonts()
    deck = sys.argv[1]
    src = pymupdf.open(str(lec.deck_pdf(deck)))
    bundle = lec.load_json(lec.bundle(deck))
    nf = lec.notes(deck)
    notes = lec.load_json(nf) if nf.exists() else {"pages": []}
    N = {p["page"]: p for p in notes.get("pages", [])}
    B = {p["page"]: p for p in bundle["pages"]}
    ulres = overlay.resolve_deck(lec, deck, notes)
    UL = ulres["pages"]

    out = pymupdf.open()
    r0 = src[0].rect
    SW, SH = r0.width, r0.height
    COLW = SW * COLW_RATIO
    PW, PH = SW + COLW, SH

    for i in range(len(src)):
        pg = i + 1
        b = B.get(pg, {"utterances": [], "dwells": [], "t_start": "", "t_end": "",
                       "seconds": 0})
        n = N.get(pg, {})

        page = out.new_page(width=PW, height=PH)
        page.insert_font(fontname=FN_R, fontfile=FONT_R)
        page.insert_font(fontname=FN_B, fontfile=FONT_B)
        page.show_pdf_page(pymupdf.Rect(0, 0, SW, SH), src, i)
        page.draw_line((SW, 0), (SW, SH), color=C_LINE, width=1)

        cont = {"k": 0}
        numfont = pymupdf.Font(fontfile=FONT_B)
        st = overlay.page_state(b)

        def draw_markers(target):
            """슬라이드 위 표시: 밑줄(읽으신 곳·강조) → '넘어가셨습니다' 도장 → 포인팅 번호 원.
            이어짐 페이지에도 같은 슬라이드가 실리므로 거기에도 똑같이 찍는다."""
            for r in UL.get(pg, []):
                col = overlay.PURPLE if r["kind"] == "emph" else overlay.CYAN
                for rc in r["rects"]:
                    x0, y0, x1, y1 = overlay.underline_geometry(rc)
                    target.draw_rect(pymupdf.Rect(x0 * SW, y0 * SH, x1 * SW, y1 * SH),
                                     color=None, fill=col, fill_opacity=0.82)
            if st["state"] == "skip":
                tw = numfont.text_length(st["label"], 13)
                box = pymupdf.Rect(SW * 0.015, SH * 0.015, SW * 0.015 + tw + 14, SH * 0.015 + 22)
                target.draw_rect(box, color=overlay.GREEN, fill=(1, 1, 1), width=1.2,
                                 fill_opacity=0.88)
                target.insert_text((box.x0 + 7, box.y0 + 16), st["label"], fontname=FN_B,
                                   fontsize=13, color=overlay.GREEN)
            for k, d in enumerate(b["dwells"], 1):
                x, y = d["nx"] * SW, d["ny"] * SH
                target.draw_circle((x, y), 8.4, color=(1, 1, 1),
                                   fill=(0.86, 0.15, 0.15), width=1.6)
                tw = numfont.text_length(str(k), 8)
                target.insert_text((x - tw / 2, y + 2.9), str(k), fontname=FN_B,
                                   fontsize=8, color=(1, 1, 1))

        def mkpage():
            cont["k"] += 1
            p2 = out.new_page(width=PW, height=PH)
            p2.insert_font(fontname=FN_R, fontfile=FONT_R)
            p2.insert_font(fontname=FN_B, fontfile=FONT_B)
            p2.show_pdf_page(pymupdf.Rect(0, 0, SW, SH), src, i)
            p2.draw_line((SW, 0), (SW, SH), color=C_LINE, width=1)
            draw_markers(p2)
            p2.insert_text((SW + PAD, PAD + 9), f"p.{pg} (이어짐 {cont['k']})",
                           fontname=FN_B, fontsize=9.6, color=C_DIM)
            return p2

        f = Flow(out, pymupdf.Rect(0, 0, SW, SH), SW + PAD, PAD + 18,
                 COLW - PAD * 2, SH - PAD * 2 - 18, mkpage)
        f.start(page)

        # 머리글
        head = f"p.{pg}"
        meta = f"{b['t_start']}–{b['t_end']} · {b['seconds']:.0f}초"
        page.insert_text((SW + PAD, PAD + 9), head, fontname=FN_B, fontsize=10.5,
                         color=C_INK)
        page.insert_text((SW + PAD + 34, PAD + 9), meta, fontname=FN_R, fontsize=7.6,
                         color=C_DIM)
        tags = []
        if n.get("is_new"):
            tags.append("올해 신규")
        if st["state"] == "skip":
            tags.append(st["label"])
        elif st["state"] == "fast":
            tags.append(st["label"])
        if tags:
            t = " · ".join(tags)
            tw = pymupdf.Font(fontfile=FONT_B).text_length(t, 7.6)
            page.insert_text((SW + COLW - PAD - tw, PAD + 9), t,
                             fontname=FN_B, fontsize=7.6, color=C_GREEN)

        draw_markers(page)

        miss = [r["text"] for r in UL.get(pg, []) if not r["ok"]]
        if miss:
            f.para("⚠ 밑줄 글자를 슬라이드에서 못 찾음: " + " · ".join(miss),
                   indent=6, color=C_RED, bar=C_RED)
        if n.get("summary"):
            f.head("■ 이 슬라이드 요지", C_GREEN)
            f.para(n["summary"], indent=6, bar=C_GREEN)
        if n.get("emphasis"):
            f.head("■ 교수님 강조", C_AMBER)
            f.para(clean_emph(n["emphasis"]), indent=6, color=(0.35, 0.22, 0.02),
                   bar=C_AMBER)
        if n.get("notes"):
            f.head("■ 필기 제안", C_BLUE)
            for x in n["notes"]:
                f.para(x["target"], indent=6, color=C_BLUE, bold=True, gap=0.5,
                       bar=C_BLUE)
                f.para("└ " + x["gloss"], indent=12, gap=3.5)
        if n.get("factcheck"):
            f.head("■ 팩트체크", C_RED)
            for x in n["factcheck"]:
                f.para(f"“{x['quote']}”", indent=6, color=C_DIM, gap=1, bar=C_RED)
                f.para(x["issue"], indent=6, color=C_RED, bold=True, gap=1)
                f.para(x["correct"], indent=6, gap=1)
                if x.get("source"):
                    f.para("근거: " + x["source"], indent=6, color=C_DIM, fs=7.2,
                           gap=4)
        fixed = apply_fixes(b["utterances"], n.get("fixes"), n.get("drops"))
        if b["dwells"]:
            f.head("■ 교수님이 짚은 곳 (슬라이드 번호와 대응)", C_RED)
            for k, d in enumerate(b["dwells"], 1):
                lab = next((p.get("label", "") for p in n.get("pointers", [])
                            if p.get("n") == k), "")
                said = (said_text(d, fixed) or "").strip()
                txt = f"({k}) " + (f"{lab} — " if lab else "") + said[:220]
                f.para(txt, indent=6, gap=2.5)

        f.rule(7)
        f.head("■ 교수님 말씀 (전문) — 빨간 번호 = 그때 짚고 계시던 지점")
        ul = fixed
        if not ul:
            f.para("— 이 페이지는 말씀 없이 넘어가셨습니다.", color=C_DIM)
        marks = dwell_marks(b["dwells"], ul)
        pfxfont = pymupdf.Font(fontfile=FONT_B)
        for ui, u in enumerate(ul):
            ks = marks.get(ui, [])
            pfx = "".join(circled(k) for k in ks) if ks else None
            ind = 4.0
            if pfx:
                ind += pfxfont.text_length(pfx, FS) + 2.0
            f.para(f"[{u['ts']}] {u['fixed']}", indent=ind, gap=1.4, pfx=pfx)

    dst = lec.outdir(deck) / (lec.stem(deck) + "_주석.pdf")
    out.save(str(dst), garbage=3, deflate=True)
    print(f"→ {dst}  ({len(out)}쪽, 원본 {len(src)}쪽, "
          f"{dst.stat().st_size/1024/1024:.1f} MB)")
    for pg, t in ulres["missing"]:
        print(f"  ⚠ p.{pg} 밑줄 글자 못 찾음: {t!r}")
    out.close()
    src.close()


if __name__ == "__main__":
    main()
