# -*- coding: utf-8 -*-
"""수업 전문 스크립트를 마크다운 한 파일로 떨군다.

페이지 구분과 타임스탬프를 그대로 달고, 팩트체크는 해당 페이지 자리에 넣는다.
맨 뒤에 ⚠ 표시가 남은 자리(음성이 뭉개져 확정 못 한 곳)를 모아 목록으로 붙인다.
사용법: python make_script_md.py <deck>
출력:  output/<수업이름>/스크립트_<수업이름>.md
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import common  # noqa: E402
from fixes import apply_fixes, circled, clean_emph, dwell_marks  # noqa: E402
import overlay  # noqa: E402


def main():
    lec = common.init()
    deck = sys.argv[1]
    b = lec.load_json(lec.bundle(deck))
    nf = lec.notes(deck)
    N = {}
    if nf.exists():
        N = {p["page"]: p for p in lec.load_json(nf)["pages"]}

    name, disp = lec.title(deck), lec.display(deck)
    L = [f"# {disp} — 수업 전문 스크립트", "",
         lec.meta_line(deck), "",
         "문장 앞의 ①②③ = 그 말을 할 때 교수님이 슬라이드에서 짚고 계시던 지점 "
         "(번호는 필기 가이드 HTML·주석 PDF의 슬라이드 위 빨간 원과 같습니다).", ""]

    tot_u = 0
    uncertain = []
    for p in b["pages"]:
        pg = p["page"]
        n = N.get(pg, {})
        ul = apply_fixes(p["utterances"], n.get("fixes"), n.get("drops"))
        tot_u += len(ul)
        head = f"## p.{pg}"
        if p["t_start"]:
            head += f"  ({p['t_start']}–{p['t_end']}, {p['seconds']:.0f}초)"
        if n.get("is_new"):
            head += "  🆕"
        st = overlay.page_state(p)
        if st["state"] == "skip":
            head += f"  🟢 {st['label']}"
        L.append(head)
        if n.get("summary"):
            L.append(f"> {n['summary']}")
            L.append("")
        if n.get("emphasis"):
            L.append(f"**🔴 {clean_emph(n['emphasis'])}**")
            L.append("")
        if not ul:
            L.append("_(말씀 없이 넘어가셨습니다)_")
            L.append("")
        marks = dwell_marks(p["dwells"], ul)
        for ui, u in enumerate(ul):
            ks = marks.get(ui, [])
            mk = ("".join(circled(k) for k in ks) + " ") if ks else ""
            L.append(f"- `{u['ts']}` {mk}{u['fixed']}")
            # ⚠[…] 중에서 '팩트체크 참고'로 연결한 것은 음성 문제가 아니므로 제외하고,
            # 소리가 뭉개져 확정하지 못한 자리만 뒤에 목록으로 모은다.
            m = re.search(r"⚠\[([^\]]*)\]", u["fixed"])
            if m and "팩트체크" not in m.group(1):
                uncertain.append((pg, u["ts"], u["fixed"]))
        L.append("")
        for f in n.get("factcheck", []):
            L.append(f"> ⚠ **팩트체크 — {f['issue']}**  ")
            L.append(f"> 발언: “{f['quote']}”  ")
            L.append(f"> {f['correct']}  ")
            if f.get("source"):
                L.append(f"> _근거: {f['source']}_")
            L.append("")

    if uncertain:
        L.append("---")
        L.append("")
        L.append("## ⚠ 확정하지 못한 구간")
        L.append("")
        L.append("음성이 뭉개져 자동 인식·재전사·자료 대조로도 확정하지 못한 자리입니다. "
                 "아래 타임스탬프만 녹화본에서 직접 확인하시면 됩니다.")
        L.append("")
        for pg, ts, txt in uncertain:
            L.append(f"- p.{pg} `{ts}` — {txt}")
        L.append("")

    dst = lec.outdir(deck) / f"스크립트_{name}.md"
    dst.write_text("\n".join(L), encoding="utf-8")
    print(f"→ {dst}  ({len(b['pages'])}쪽, 발화 {tot_u}건, ⚠ {len(uncertain)}곳)")


if __name__ == "__main__":
    main()
