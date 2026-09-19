# -*- coding: utf-8 -*-
"""오늘 수업 PDF에서 페이지별 텍스트를 뽑아 _work/slides.json 으로 저장.
- whisper initial_prompt(의학 용어 편향)용
- 슬라이드↔페이지 매칭 및 최종 필기 가이드용

pypdf 를 쓴다(pymupdf로 바꾸면 추출 텍스트가 달라져 whisper 프롬프트·결과 재현성이 깨진다).
사용법: python extract_slides.py [--lecture <폴더>]
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import common  # noqa: E402

from pypdf import PdfReader  # noqa: E402


def main():
    lec = common.init()
    out = {}
    for d in lec.decks():
        r = PdfReader(str(lec.root / d.pdf))
        pages = []
        for i, p in enumerate(r.pages, 1):
            t = (p.extract_text() or "").strip()
            t = re.sub(r"[ \t]+", " ", t)
            t = re.sub(r"\n{3,}", "\n\n", t)
            pages.append({"page": i, "text": t})
        out[d.key] = {"file": d.pdf, "n_pages": len(pages), "pages": pages}
        empty = sum(1 for x in pages if not x["text"])
        print(f"{d.key}: {len(pages)}p (텍스트 없는 페이지 {empty}개)")

    lec.work.mkdir(exist_ok=True)
    lec.slides_json.write_text(json.dumps(out, ensure_ascii=False, indent=1),
                               encoding="utf-8")
    print("→", lec.slides_json)


if __name__ == "__main__":
    main()
