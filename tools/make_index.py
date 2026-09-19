# -*- coding: utf-8 -*-
"""output 폴더 첫 화면(index.html)을 만든다 — 수업별 산출물로 들어가는 입구 + 사용법.
사용법: python make_index.py
"""
import html
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import common  # noqa: E402
import overlay  # noqa: E402

CSS = """
:root{--bg:#f6f7f9;--card:#fff;--ink:#1c1f24;--dim:#6b7280;--line:#e3e6ea;--blue:#1d4ed8}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
 font-family:"Pretendard","Malgun Gothic","맑은 고딕",system-ui,sans-serif;line-height:1.75}
.wrap{max-width:1000px;margin:0 auto;padding:34px 20px 60px}
h1{font-size:26px;margin:0 0 4px}
.sub{color:var(--dim);font-size:14px;margin-bottom:26px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;
 padding:18px 20px;margin-bottom:16px}
.card h2{font-size:19px;margin:0 0 3px}
.card .meta{color:var(--dim);font-size:13px;margin-bottom:12px}
.stat{display:flex;gap:16px;flex-wrap:wrap;font-size:13px;color:#4b5563;margin-bottom:13px}
.stat b{color:var(--ink)}
a.btn{display:inline-block;padding:8px 15px;border-radius:8px;text-decoration:none;
 font-size:14px;font-weight:600;margin-right:8px;margin-bottom:6px}
a.p{background:#111;color:#fff}
a.s{background:#eef3ff;color:var(--blue);border:1px solid #cfdcff}
a.g{background:#f0fdf4;color:#15803d;border:1px solid #bbf7d0}
.skip{font-size:13px;color:#15803d;margin:-6px 0 12px}
.skip b{color:#15803d}
.how{background:#fff;border:1px solid var(--line);border-radius:14px;padding:18px 22px;
 margin-top:24px}
.how h2{font-size:17px;margin:0 0 10px}
.how ol{margin:0;padding-left:20px}
.how li{margin-bottom:9px}
.how code{background:#f1f3f5;padding:1px 6px;border-radius:4px;font-size:13px}
.note{font-size:13.5px;color:var(--dim);margin-top:18px;line-height:1.7}
"""


def esc(s):
    return html.escape(str(s))


def main():
    lec = common.init()
    rows = []
    for d in lec.decks():
        key, name, period, span, stem = d.key, d.name, d.period, lec.span_text(d.key), d.stem
        b = lec.load_json(lec.bundle(key))
        nf = lec.notes(key)
        n = lec.load_json(nf) if nf.exists() else {"pages": []}
        npages = len(b["pages"])
        nutt = sum(len(p["utterances"]) for p in b["pages"])
        nchar = sum(p["chars"] for p in b["pages"])
        ndw = sum(len(p["dwells"]) for p in b["pages"])
        nfc = sum(len(p.get("factcheck", [])) for p in n["pages"])
        nnote = sum(len(p.get("notes", [])) for p in n["pages"])
        nul = sum(1 for p in n["pages"] if p.get("underline"))
        skipped = [p["page"] for p in b["pages"] if overlay.page_state(p)["state"] == "skip"]
        skip_line = (f'<div class="skip">🟢 말씀 없이 넘어가신 페이지 <b>{len(skipped)}쪽</b>: '
                     f'{", ".join(map(str, skipped))}</div>' if skipped else "")
        writeup = lec.out / name / f"글작성_초안_{name}.txt"
        writeup_btn = (f'\n <a class="btn g" href="{esc(name)}/글작성_초안_{esc(name)}.txt">'
                       f'📋 글작성 초안 (txt)</a>' if writeup.exists() else "")
        tablet = lec.out / name / f"필기가이드_{name}_태블릿.html"
        tablet_btn = (f'\n <a class="btn s" href="{esc(name)}/필기가이드_{esc(name)}_태블릿.html">'
                      f'📱 태블릿용 HTML (파일 하나, {tablet.stat().st_size/1024/1024:.0f}MB)</a>'
                      if tablet.exists() else "")
        rows.append(f"""<div class="card">
 <h2>{esc(name.replace('_', ' '))}</h2>
 <div class="meta">{esc(lec.date)} {esc(period)} · {esc(lec.professor)} 교수님 · 녹화본 {esc(span)}</div>
 <div class="stat">
  <span>슬라이드 <b>{npages}쪽</b></span>
  <span>발화 <b>{nutt}건</b> ({nchar:,}자)</span>
  <span>마우스 포인팅 <b>{ndw}곳</b></span>
  <span>필기 제안 <b>{nnote}개</b></span>
  <span>밑줄 <b>{nul}쪽</b></span>
  <span>⚠ 팩트체크 <b>{nfc}건</b></span>
 </div>{skip_line}
 <a class="btn p" href="{esc(name)}/필기가이드_{esc(name)}.html">📝 필기 가이드 (HTML)</a>
 <a class="btn s" href="{esc(name)}/{esc(stem)}_주석.pdf">📄 주석 PDF</a>
 <a class="btn s" href="{esc(name)}/스크립트_{esc(name)}.md">📃 스크립트 전문 (md)</a>{tablet_btn}{writeup_btn}
</div>""")

    extra_notes = "".join(f"<br>\n · {esc(x)}" for x in lec.index_notes)
    H = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(lec.date)} {esc(lec.course)} 수업 필기 자료</title>
<style>{CSS}</style></head><body><div class="wrap">
<h1>{esc(lec.date)} {esc(lec.course)} · {esc(lec.professor)} 교수님</h1>
<div class="sub">녹화본에서 뽑은 수업 전문 + 슬라이드 페이지별 묶음 + 마우스로 짚은 지점 표시</div>
{''.join(rows)}
<div class="how">
 <h2>어떻게 쓰면 되나</h2>
 <ol>
  <li><b>필기 가이드(HTML)</b>를 브라우저로 엽니다. 슬라이드 한 쪽마다
      ① 요지 ② 교수님 강조 ③ 작년 형식의 필기 제안 ④ ⚠ 팩트체크
      ⑤ 교수님이 마우스로 짚은 곳 ⑥ 말씀 전문이 함께 있습니다.</li>
  <li>슬라이드 그림 위의 <b>빨간 번호</b>가 교수님이 마우스를 멈춘 지점입니다.
      번호를 <b>클릭</b>하면 그때 하신 말씀이 아래에서 노랗게 표시됩니다.</li>
  <li>그대로 옮겨 적을 것은 <b>필기 제안</b> 칸입니다. 작년 필기처럼
      「용어 → └ 설명」 형식이라 PPT 텍스트 상자에 그대로 붙이면 됩니다.</li>
  <li><b>주석 PDF</b>는 태블릿에서 보기 좋습니다. 원본 슬라이드 오른쪽에
      같은 내용이 붙어 있고, 슬라이드 위에는 포인팅 번호가 찍혀 있습니다.</li>
  <li><b>⚠ 팩트체크</b>는 그대로 필기하면 안 되는 자리입니다. 근거와 함께
      바로잡을 내용을 적어 두었습니다.</li>
  <li>슬라이드 위 <b>하늘색 밑줄</b> = 교수님이 읽으신 부분, <b>보라색 밑줄</b> = 강조,
      초록 <b>「넘어가셨습니다」</b> = 말씀 없이 지나간 슬라이드 — 손필기 색 규칙과 같게 맞춰 두었으니
      그대로 옮기면 됩니다. <b>글작성 초안</b>은 올릴 때 쓰는 강조·추가·변경 페이지 목록입니다.</li>
 </ol>
</div>
<div class="note">
 · 스크립트의 <code>⚠[…]</code> 표시는 음성이 뭉개져 확정하지 못한 부분입니다.
   그 타임스탬프만 녹화본에서 직접 확인하시면 됩니다.<br>
 · 「원 인식」으로 접혀 있는 회색 글씨는 교정 전 자동 인식 결과입니다 —
   교정이 맞는지 대조해 보실 수 있게 남겨 두었습니다.{extra_notes}
</div>
</div></body></html>"""

    lec.out.mkdir(parents=True, exist_ok=True)
    (lec.out / "index.html").write_text(H, encoding="utf-8")
    print(f"→ {lec.out / 'index.html'}")


if __name__ == "__main__":
    main()
