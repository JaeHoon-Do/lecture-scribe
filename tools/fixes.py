# -*- coding: utf-8 -*-
"""교정본 적용 규칙 (HTML·PDF 렌더러 공용).

notes_<deck>.json의 pages[].fixes = [{"ts": "01:45:04", "text": "교정된 문장"}, …]
를 bundle의 발화 목록에 붙인다. 위치 인덱스가 아니라 타임스탬프로 맞추므로,
전사를 다시 돌려 발화 개수가 달라져도 교정본이 어긋나지 않는다.
같은 타임스탬프가 여럿이면 나온 순서대로 짝지운다.
"""


def clean_emph(s: str) -> str:
    """강조문 앞의 🔴는 렌더러가 따로 붙이므로 원문에 있으면 떼어 낸다(중복 방지)."""
    t = (s or "").strip()
    while t.startswith("🔴"):
        t = t[1:].lstrip()
    return t


def said_text(dwell, fixed_list):
    """dwell이 가리키는 발화를 교정본으로 바꿔 돌려준다.
    (마커 설명과 아래 전문이 서로 다른 문장을 보여주면 헷갈리므로 같은 것을 쓴다)"""
    ts = dwell.get("said_ts")
    if ts:
        for u in fixed_list:
            if u["ts"] == ts:
                return u["fixed"]
    return dwell.get("said", "")


def apply_fixes(utterances, fixes, drops=None):
    """[{ts,text,t,te,…}] + [{ts,text}] → [{…, 'fixed': 최종문장}]

    drops = 버릴 발화의 타임스탬프 목록. 갭 보충 과정에서 옆 문장을 다시 받아쓴
    중복분을 걸러내고 남은 것을 사람이 확인해 지정한다(자동 필터가 놓친 몫).
    """
    drop = set(drops or [])
    pool = {}
    for f in (fixes or []):
        pool.setdefault(f["ts"], []).append(f["text"])
    used = {}
    out = []
    for u in utterances:
        if u["ts"] in drop and u.get("filled"):
            continue
        v = dict(u)
        ts = u["ts"]
        i = used.get(ts, 0)
        cand = pool.get(ts, [])
        v["fixed"] = cand[i] if i < len(cand) else u["text"]
        used[ts] = i + 1
        out.append(v)
    return out


CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮"


def circled(k: int) -> str:
    """1→① … 15→⑮ (맑은 고딕에 다 들어 있다). 넘어가면 (16) 처럼."""
    return CIRCLED[k - 1] if 1 <= k <= len(CIRCLED) else f"({k})"


def dwell_marks(dwells, ulist):
    """발화 index → 그때 교수님이 마우스로 짚고 있던 마커 번호 목록.

    누르지 않아도 전문에서 '이 문장을 할 때 ③을 가리키고 있었다'가 보이게 하려고
    쓴다. 판정 기준은 두 가지를 합집합으로 둔다.
      ① 시간 겹침 — dwell 구간(t0~t1)과 발화 구간(t~te)이 실제로 겹치는 발화
      ② said_ts   — assemble이 그 dwell에 가장 잘 맞다고 고른 발화(겹침이 없어도 포함)
    겹침이 하나도 안 잡히는 dwell(발화 사이 침묵 중에 짚은 경우)도 ②로 한 군데는
    반드시 붙으므로, 슬라이드의 모든 번호가 전문 어딘가에서 회수된다.
    """
    marks = {}
    for k, d in enumerate(dwells, 1):
        s, e = d.get("t0"), d.get("t1")
        hit = set()
        if s is not None and e is not None:
            for i, u in enumerate(ulist):
                if u["t"] < e and u["te"] > s:
                    hit.add(i)
        ts = d.get("said_ts")
        if ts:
            for i, u in enumerate(ulist):
                if u["ts"] == ts:
                    hit.add(i)
                    break
        if not hit and ulist:
            # 발화와 발화 사이(짧은 침묵)에 짚은 dwell — 가장 가까운 발화에 붙인다.
            # 4초를 넘어가면 엉뚱한 문장에 달리므로 그냥 포기한다(포인팅 목록에는 남는다).
            j, gap = min(
                ((i, max(0.0, max(s - u["te"], u["t"] - e)))
                 for i, u in enumerate(ulist)), key=lambda x: x[1])
            if gap <= 4.0:
                hit.add(j)
        for i in hit:
            marks.setdefault(i, []).append(k)
    for i in marks:
        marks[i].sort()
    return marks
