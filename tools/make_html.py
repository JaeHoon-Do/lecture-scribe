# -*- coding: utf-8 -*-
"""페이지별 필기 가이드 HTML을 만든다.

입력: _work/bundle_<deck>.json  (페이지별 발화·dwell — 기계가 만든 것)
      _work/notes_<deck>.json   (교정 스크립트·필기 제안·팩트체크 — Claude가 쓴 것)
출력: output/<수업이름>/필기가이드_<수업이름>.html
        슬라이드 이미지는 output/_slides/<deck>/ 를 상대경로로 참조 (HTML 자체는 가볍게)
      output/<수업이름>/필기가이드_<수업이름>_태블릿.html   (--tablet)
        슬라이드 이미지를 base64 로 내장한 파일 하나짜리 — iPad 파일앱/갤럭시탭에서 바로 열림.
        태블릿 가로모드 전용 배치: 왼쪽 좁은 열에 슬라이드(원본은 옆 기기에 있으므로 작게, 스크롤해도 고정),
        오른쪽 넓은 열에 필기 제안·전문. 「원 인식」(교정 전 whisper 인식문)은 기본 표시, 버튼으로 숨김.
사용법: python make_html.py <deck> [--tablet]
"""
import base64
import html
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import common  # noqa: E402
from fixes import apply_fixes, clean_emph, dwell_marks, said_text  # noqa: E402
import overlay  # noqa: E402

CSS = """
:root{
 --bg:#f6f7f9; --card:#fff; --ink:#1c1f24; --dim:#6b7280; --line:#e3e6ea;
 --blue:#1d4ed8; --bluebg:#eef3ff; --red:#c0392b; --redbg:#fdeeec;
 --amber:#a16207; --amberbg:#fef7e6; --green:#0f766e; --greenbg:#e9f7f5;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
 font-family:"Pretendard","Malgun Gothic","맑은 고딕",system-ui,sans-serif;
 font-size:15px;line-height:1.7}
header{position:sticky;top:0;z-index:50;background:#fff;border-bottom:2px solid #111;
 padding:10px 18px;display:flex;gap:14px;align-items:center;flex-wrap:wrap}
header h1{font-size:17px;margin:0;font-weight:800}
header .meta{color:var(--dim);font-size:13px}
header .stat{margin-left:auto;font-size:13px;color:var(--dim)}
#jump{padding:6px 8px;font-size:13px;max-width:260px}
.wrap{max-width:1500px;margin:0 auto;padding:18px}
.page{background:var(--card);border:1px solid var(--line);border-radius:12px;
 margin-bottom:22px;overflow:hidden;scroll-margin-top:64px}
.phead{display:flex;align-items:center;gap:10px;padding:9px 14px;
 background:#111;color:#fff;font-size:14px;font-weight:700}
.phead .t{margin-left:auto;font-weight:400;color:#c9cdd3;font-size:13px}
.pbody{display:grid;grid-template-columns:minmax(430px,1.05fr) 1.35fr;gap:0}
@media(max-width:1100px){.pbody{grid-template-columns:1fr}}
.left{padding:14px;border-right:1px solid var(--line);background:#fafbfc}
.slide{position:relative;display:inline-block;width:100%}
.slide img{width:100%;display:block;border:1px solid var(--line);border-radius:6px}
.mk{position:absolute;transform:translate(-50%,-50%);width:26px;height:26px;
 border-radius:50%;background:rgba(220,38,38,.86);color:#fff;font-size:13px;
 font-weight:700;display:flex;align-items:center;justify-content:center;
 border:2px solid #fff;cursor:pointer;box-shadow:0 1px 4px rgba(0,0,0,.35)}
.mk:hover,.mk.on{background:#111;transform:translate(-50%,-50%) scale(1.22)}
.ul{position:absolute;pointer-events:none;border-radius:3px}
.ul.ul-read{background:rgba(102,212,238,.82)}
.ul.ul-emph{background:rgba(158,92,219,.82)}
.stamp{position:absolute;left:1.5%;top:1.5%;pointer-events:none;color:#16a34a;
 font-weight:800;font-size:15px;background:rgba(255,255,255,.88);padding:2px 9px;
 border-radius:6px;border:1.5px solid #16a34a}
.right{padding:14px 16px}
h3{font-size:13px;margin:0 0 7px;letter-spacing:.4px;color:var(--dim);
 text-transform:uppercase;font-weight:800}
.sec{margin-bottom:16px}
.note{background:var(--bluebg);border-left:4px solid var(--blue);
 padding:9px 12px;border-radius:0 6px 6px 0;margin-bottom:7px}
.note .tg{font-weight:700;color:var(--blue)}
.note .gl{display:block;margin-top:2px}
.sum{background:var(--greenbg);border-left:4px solid var(--green);
 padding:10px 12px;border-radius:0 6px 6px 0;margin-bottom:10px}
.emph{background:var(--amberbg);border-left:4px solid var(--amber);
 padding:9px 12px;border-radius:0 6px 6px 0;margin-bottom:10px}
.fc{background:var(--redbg);border-left:4px solid var(--red);
 padding:10px 12px;border-radius:0 6px 6px 0;margin-bottom:8px}
.fc b{color:var(--red)}
.fc .q{color:#555;font-style:italic}
.fc .src{font-size:12px;color:var(--dim);display:block;margin-top:3px}
.script{border:1px solid var(--line);border-radius:8px;background:#fcfcfd;
 max-height:520px;overflow:auto}
.u{display:flex;gap:9px;padding:5px 11px;border-bottom:1px solid #f0f1f3}
.u:last-child{border-bottom:0}
.u .ts{color:#9aa1ab;font-size:11.5px;font-variant-numeric:tabular-nums;
 flex:0 0 60px;padding-top:3px}
.u .tx{flex:1}
.u.hl{background:#fff8dc}
.u .raw{display:block;color:#9aa1ab;font-size:12px;margin-top:2px}
.u .mkref{flex:0 0 auto;display:flex;gap:2px;padding-top:3px}
.u .mkref b{display:inline-flex;align-items:center;justify-content:center;
 width:18px;height:18px;border-radius:50%;background:#dc2626;color:#fff;
 font-size:11px;font-weight:700;cursor:pointer}
.u .mkref b:hover{background:#111}
.u.pointed{background:#fff6f5}
.pt{display:flex;gap:9px;padding:6px 0;border-bottom:1px dashed #e8eaed}
.pt:last-child{border-bottom:0}
.pt .n{flex:0 0 24px;height:24px;border-radius:50%;background:#dc2626;color:#fff;
 font-size:12px;font-weight:700;display:flex;align-items:center;justify-content:center}
.pt .d{flex:1}
.pt .d .lab{font-weight:600}
.pt .d .said{color:#555;font-size:13.5px}
.empty{color:var(--dim);font-size:13.5px;padding:6px 0}
.badge{display:inline-block;font-size:11.5px;padding:1px 7px;border-radius:99px;
 background:#eef1f4;color:#4b5563;margin-left:6px;font-weight:600}
.badge.new{background:#dcfce7;color:#166534}
.badge.warn{background:#fee2e2;color:#991b1b}
.badge.skip{background:#dcfce7;color:#15803d}
.ulmiss{background:#fff1f2;border-left:4px solid #e11d48;padding:7px 12px;
 border-radius:0 6px 6px 0;margin-bottom:10px;font-size:13.5px}
.toc{background:#fff;border:1px solid var(--line);border-radius:12px;padding:14px 16px;
 margin-bottom:20px}
.toc h2{font-size:15px;margin:0 0 9px}
.toc a{display:inline-block;padding:2px 7px;margin:2px;border-radius:5px;
 font-size:12.5px;text-decoration:none;color:#374151;background:#f1f3f5}
.toc a:hover{background:#111;color:#fff}
.toc a.has{background:#fee2e2;color:#991b1b}
.toc a.skip{background:#dcfce7;color:#15803d}
.legend{font-size:12.5px;color:var(--dim);margin-top:8px}
"""

# 태블릿(가로모드): 슬라이드는 왼쪽 좁은 열에 작게·고정(sticky), 오른쪽 넓은 열에 필기·전문.
# 전문 높이 제한 해제, 「원 인식」은 기본 표시(버튼으로 숨김). 세로로 돌리면(폭 760px 미만) 1열.
TABLET_CSS = """
body{font-size:16px}
header{padding:8px 14px}
header .stat{display:none}
.wrap{max-width:none;padding:8px 10px}
.page{margin-bottom:14px;scroll-margin-top:58px}
.pbody{grid-template-columns:minmax(280px,29%) 1fr}
.left{padding:10px;position:sticky;top:54px;align-self:start}
.right{padding:12px 16px}
.script{max-height:none}
.mk{width:26px;height:26px;font-size:12.5px}
.stamp{font-size:12px;padding:1px 7px}
.u{padding:6px 11px}
.u .mkref b{width:22px;height:22px;font-size:12px}
.u .raw{font-size:13px}
body.hideraw .u .raw{display:none}
#rawtoggle{font-size:13px;padding:6px 10px;border:1px solid #999;border-radius:6px;background:#111;color:#fff}
body.hideraw #rawtoggle{background:#fff;color:#111}
@media(max-width:760px){.pbody{grid-template-columns:1fr}
 .left{position:static;border-right:0;border-bottom:1px solid var(--line)}}
"""

JS = """
document.addEventListener('click',e=>{
 const m=e.target.closest('.mk'); if(!m) return;
 const pg=m.dataset.pg, k=m.dataset.k;
 document.querySelectorAll('.mk.on').forEach(x=>x.classList.remove('on'));
 document.querySelectorAll('.u.hl').forEach(x=>x.classList.remove('hl'));
 m.classList.add('on');
 const row=document.querySelector(`#pt-${pg}-${k}`);
 if(row){row.scrollIntoView({block:'nearest',behavior:'smooth'});
   row.style.background='#fff8dc';setTimeout(()=>row.style.background='',1600);}
 document.querySelectorAll(`.u[data-pg="${pg}"]`).forEach(u=>{
   const a=+u.dataset.t0,b=+u.dataset.t1,s=+m.dataset.s,t=+m.dataset.e;
   if(a-2.5<=t&&b+2.5>=s) u.classList.add('hl');
 });
});
document.addEventListener('click',e=>{
 const b=e.target.closest('.mkref b'); if(!b) return;
 const [pg,k]=b.dataset.goto.split('-');
 const mk=document.querySelector(`.mk[data-pg="${pg}"][data-k="${k}"]`);
 if(!mk) return;
 document.querySelectorAll('.mk.on').forEach(x=>x.classList.remove('on'));
 mk.classList.add('on');
 mk.scrollIntoView({block:'center',behavior:'smooth'});
});
document.getElementById('jump').addEventListener('change',e=>{
 const v=e.target.value; if(v) document.getElementById('p'+v).scrollIntoView({behavior:'smooth'});
});
"""

TABLET_JS = """
document.getElementById('rawtoggle').addEventListener('click',e=>{
 const hide=document.body.classList.toggle('hideraw');
 e.target.textContent=hide?'원 인식 보기':'원 인식 숨기기';
});
"""


def esc(s):
    return html.escape(str(s or ""))


def build_html(lec, deck, bundle, notes, img_src, tablet=False, ul=None) -> str:
    """bundle+notes → HTML 문자열. img_src(pg) 가 <img src> 값을 돌려준다.
    ul = overlay.resolve_deck() 결과(밑줄 좌표). None 이면 직접 계산."""
    N = {p["page"]: p for p in notes.get("pages", [])}
    disp = lec.display(deck)
    if ul is None:
        ul = overlay.resolve_deck(lec, deck, notes)
    UL = ul["pages"]
    ST = {p["page"]: overlay.page_state(p) for p in bundle["pages"]}

    tot_u = sum(len(p["utterances"]) for p in bundle["pages"])
    tot_d = sum(len(p["dwells"]) for p in bundle["pages"])
    n_fc = sum(len(N.get(p["page"], {}).get("factcheck", [])) for p in bundle["pages"])
    n_ul = sum(len(r["rects"]) for v in UL.values() for r in v)
    n_skip = sum(1 for s in ST.values() if s["state"] == "skip")

    css = CSS + (TABLET_CSS if tablet else "")
    H = [f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(disp)} 필기 가이드 — {esc(lec.date)} {esc(lec.professor)}</title>
<style>{css}</style></head><body>
<header>
 <h1>📝 {esc(disp)}</h1>
 <span class="meta">{esc(lec.meta_line(deck))}</span>
 <select id="jump"><option value="">페이지로 이동…</option>"""]
    for p in bundle["pages"]:
        mark = " ⚠" if N.get(p["page"], {}).get("factcheck") else ""
        H.append(f'<option value="{p["page"]}">p.{p["page"]}{mark}</option>')
    H.append("</select>")
    if tablet:
        H.append('<button id="rawtoggle" type="button">원 인식 숨기기</button>')
    H.append(f"""
 <span class="stat">{len(bundle["pages"])}쪽 · 발화 {tot_u}건 · 포인팅 {tot_d}개 · 밑줄 {n_ul}곳 · 넘어감 {n_skip}쪽 · 팩트체크 {n_fc}건</span>
</header><div class="wrap">""")

    # 목차
    H.append('<div class="toc"><h2>📑 페이지 바로가기</h2>')
    for p in bundle["pages"]:
        cls = ""
        if N.get(p["page"], {}).get("factcheck"):
            cls = " has"
        elif ST[p["page"]]["state"] == "skip":
            cls = " skip"
        H.append(f'<a class="jl{cls}" href="#p{p["page"]}">{p["page"]}</a>')
    H.append('<div class="legend">빨간 번호 = 교수님 발언에 팩트체크 표시가 붙은 페이지 · '
             '초록 번호 = 말씀 없이 넘어가신 페이지 · '
             '슬라이드 위 빨간 원 = 교수님이 마우스로 짚은 지점(클릭하면 그때 한 말로 이동) · '
             '전문 왼쪽의 빨간 번호 = 그 문장을 말할 때 짚고 있던 지점(눌러 보지 않아도 표시됨)<br>'
             '슬라이드 위 <b style="background:' + overlay.CYAN_CSS + ';padding:0 6px">하늘색 밑줄</b> = 교수님이 읽으신 부분 · '
             '<b style="background:' + overlay.PURPLE_CSS + ';padding:0 6px;color:#fff">보라색 밑줄</b> = 강조 · '
             '<b style="color:' + overlay.GREEN_CSS + '">초록 도장</b> = 넘어가셨습니다 (손필기 색 규칙과 같음)</div></div>')

    for p in bundle["pages"]:
        pg = p["page"]
        n = N.get(pg, {})
        img = img_src(pg)
        H.append(f'<section class="page" id="p{pg}">')
        badges = ""
        if n.get("is_new"):
            badges += '<span class="badge new">올해 신규</span>'
        if n.get("factcheck"):
            badges += f'<span class="badge warn">팩트체크 {len(n["factcheck"])}</span>'
        st = ST[pg]
        if st["state"] == "skip":
            badges += f'<span class="badge skip">{esc(st["label"])}</span>'
        elif st["state"] == "fast":
            badges += f'<span class="badge">{esc(st["label"])}</span>'
        H.append(f'<div class="phead">p.{pg}{badges}'
                 f'<span class="t">{esc(p["t_start"])} – {esc(p["t_end"])} · {p["seconds"]:.0f}초</span></div>')
        H.append('<div class="pbody"><div class="left"><div class="slide">')
        H.append(f'<img src="{img}" alt="p.{pg}" loading="lazy">')
        for r in UL.get(pg, []):
            for rc in r["rects"]:
                x0, y0, x1, y1 = overlay.underline_geometry(rc)
                H.append(f'<div class="ul ul-{r["kind"]}" title="{esc(r["text"])}" '
                         f'style="left:{x0*100:.2f}%;top:{y0*100:.2f}%;'
                         f'width:{(x1-x0)*100:.2f}%;height:{(y1-y0)*100:.2f}%"></div>')
        if st["state"] == "skip":
            H.append(f'<div class="stamp">{esc(st["label"])}</div>')
        for k, d in enumerate(p["dwells"], 1):
            H.append(f'<div class="mk" data-pg="{pg}" data-k="{k}" '
                     f'data-s="{d["t0"]}" data-e="{d["t1"]}" '
                     f'style="left:{d["nx"]*100:.2f}%;top:{d["ny"]*100:.2f}%" '
                     f'title="{d["dur"]}초 머묾">{k}</div>')
        H.append('</div></div><div class="right">')

        miss = [r["text"] for r in UL.get(pg, []) if not r["ok"]]
        if miss:
            H.append('<div class="ulmiss">⚠ 밑줄 글자를 슬라이드에서 못 찾음: '
                     + " · ".join(esc(m) for m in miss) + '</div>')
        if n.get("summary"):
            H.append(f'<div class="sum"><b>이 슬라이드 요지</b><br>{esc(n["summary"])}</div>')
        if n.get("emphasis"):
            H.append('<div class="emph"><b>🔴 교수님 강조</b><br>'
                     f'{esc(clean_emph(n["emphasis"]))}</div>')

        if n.get("notes"):
            H.append('<div class="sec"><h3>✍ 필기 제안 (작년 형식)</h3>')
            for x in n["notes"]:
                H.append(f'<div class="note"><span class="tg">{esc(x["target"])}</span>'
                         f'<span class="gl">└ {esc(x["gloss"])}</span></div>')
            H.append('</div>')

        if n.get("factcheck"):
            H.append('<div class="sec"><h3>⚠ 팩트체크</h3>')
            for f in n["factcheck"]:
                H.append(f'<div class="fc"><span class="q">“{esc(f["quote"])}”</span><br>'
                         f'<b>{esc(f["issue"])}</b><br>{esc(f["correct"])}'
                         + (f'<span class="src">근거: {esc(f["source"])}</span>'
                            if f.get("source") else "") + '</div>')
            H.append('</div>')

        ulist = apply_fixes(p["utterances"], n.get("fixes"), n.get("drops"))
        marks = dwell_marks(p["dwells"], ulist)
        if p["dwells"]:
            H.append('<div class="sec"><h3>🖱 교수님이 짚은 곳</h3>')
            for k, d in enumerate(p["dwells"], 1):
                lab = ""
                for pt in n.get("pointers", []):
                    if pt.get("n") == k:
                        lab = pt.get("label", "")
                said = said_text(d, ulist)[:260]
                H.append(f'<div class="pt" id="pt-{pg}-{k}"><div class="n">{k}</div><div class="d">'
                         + (f'<div class="lab">{esc(lab)}</div>' if lab else "")
                         + f'<div class="said">{esc(said)}</div></div></div>')
            H.append('</div>')

        H.append('<div class="sec"><h3>🎙 교수님 말씀 (전문)</h3><div class="script">')
        if not ulist:
            H.append('<div class="empty">이 페이지에서는 말씀이 없었습니다 '
                     '(넘어가셨습니다).</div>')
        for i, u in enumerate(ulist):
            raw, txt = u["text"], u["fixed"]
            ks = marks.get(i, [])
            ref = ""
            if ks:
                ref = '<div class="mkref">' + "".join(
                    f'<b data-goto="{pg}-{k}" title="이 말을 할 때 슬라이드의 '
                    f'{k}번을 짚고 계셨습니다">{k}</b>' for k in ks) + '</div>'
            H.append(f'<div class="u{" pointed" if ks else ""}" data-pg="{pg}" '
                     f'data-t0="{u["t"]}" data-t1="{u["te"]}">'
                     f'<div class="ts">{esc(u["ts"])}</div>{ref}'
                     f'<div class="tx">{esc(txt)}'
                     + (f'<span class="raw">원 인식: {esc(raw)}</span>'
                        if raw != txt else "")
                     + '</div></div>')
        H.append('</div></div>')
        H.append('</div></div></section>')

    js = JS + (TABLET_JS if tablet else "")
    H.append(f'</div><script>{js}</script></body></html>')
    return "".join(H)


def main():
    lec = common.init()
    tablet = "--tablet" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    deck = args[0]
    bundle = lec.load_json(lec.bundle(deck))
    nf = lec.notes(deck)
    notes = lec.load_json(nf) if nf.exists() else {"pages": []}

    name = lec.title(deck)
    outdir = lec.outdir(deck)
    ul = overlay.resolve_deck(lec, deck, notes)

    if tablet:
        import pymupdf
        from render_pages import render_page_bytes
        w, q = common.render_cfg("tablet")
        doc = pymupdf.open(str(lec.deck_pdf(deck)))
        cache = {}

        def img_src(pg):
            if pg not in cache:
                b = render_page_bytes(doc, pg - 1, w, q)
                cache[pg] = "data:image/jpeg;base64," + base64.b64encode(b).decode("ascii")
            return cache[pg]
        dst = outdir / f"필기가이드_{name}_태블릿.html"
    else:
        rel = f"../_slides/{deck}"

        def img_src(pg):
            return f"{rel}/{pg:03d}.jpg"
        dst = outdir / f"필기가이드_{name}.html"

    dst.write_text(build_html(lec, deck, bundle, notes, img_src, tablet, ul), encoding="utf-8")
    kb = dst.stat().st_size / 1024
    print(f"→ {dst}  ({kb:.0f} KB, {len(bundle['pages'])}쪽{', 태블릿용 단일 파일' if tablet else ''})")
    for pg, t in ul["missing"]:
        print(f"  ⚠ p.{pg} 밑줄 글자 못 찾음: {t!r}")


if __name__ == "__main__":
    main()
