# -*- coding: utf-8 -*-
"""작년 필기 PDF ↔ 올해 슬라이드 페이지 대응을 단조 정렬(DP)로 확정한다.

작년 것은 손글씨가 덧그려져 있어 유사도가 낮아지지만 같은 슬라이드끼리는 여전히 최고점이고,
'둘 다 앞으로 진행한다'는 제약을 DP로 넣으면 표지 한 장 때문에 밀린 것도 잡힌다.

출력: _work/lastyear_map.json   { deck: { "올해p": [작년p, …] } }   ← dump_bundle 등이 읽는 정본
      _work/lastyear_scores.json { deck: { "올해p": 유사도 } }        ← make_writeup 의 '변경 후보' 판단용
      (--report 를 주면 _work/lastyear_align_report.json 에 '같은 번호가 최고점이 아닌 페이지' 보고서도 남긴다)
사용법: python lastyear_map.py [--report]
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
import common  # noqa: E402

CW, CH = 128, 96


def vec(p):
    v = np.asarray(Image.open(p).convert("L").resize((CW, CH), Image.BILINEAR),
                   dtype=np.float32).ravel()
    v -= v.mean()
    n = np.linalg.norm(v)
    return v / n if n > 1e-6 else v


def dp(S):
    N, P = S.shape
    best = np.full((N, P), -1e9)
    back = np.zeros((N, P), dtype=int)
    best[0] = S[0]
    for i in range(1, N):
        run, arg = -1e9, 0
        for j in range(P):
            if best[i - 1, j] > run:
                run, arg = best[i - 1, j], j
            best[i, j] = S[i, j] + run
            back[i, j] = arg
    j = int(np.argmax(best[-1]))
    path = [j]
    for i in range(N - 1, 0, -1):
        j = int(back[i, j])
        path.append(j)
    return path[::-1]


def main():
    lec = common.init()
    report = "--report" in sys.argv
    out, rep, scores = {}, {}, {}
    for deck in lec.keys():
        today = sorted(lec.pages_dir(deck).glob("*.jpg"))
        last = sorted(lec.lastyear_dir(deck).glob("*.jpg"))
        if not today:
            sys.exit(f"{deck}: 올해 페이지 렌더가 없습니다 (render_pages.py match)")
        if not last:
            print(f"{deck}: 작년 필기 렌더 없음 → 전부 '올해 신규'로 둠")
            out[deck] = {}
            scores[deck] = {}
            continue
        T = np.stack([vec(f) for f in today])
        L = np.stack([vec(f) for f in last])
        S = L @ T.T
        path = dp(S)
        m = {}          # 올해 페이지 → 작년 필기 페이지
        rows = []
        for i, j in enumerate(path):
            lastp, todayp = i + 1, j + 1
            rows.append(f"{lastp}->{todayp}")
            m.setdefault(todayp, []).append(lastp)
        print(f"{deck}: 작년{len(last)}p→올해{len(today)}p, 커버 {len(m)}/{len(today)}")
        print("   " + " ".join(rows[:40]))
        if len(rows) > 40:
            print("   " + " ".join(rows[40:]))
        out[deck] = {str(k): v for k, v in m.items()}
        scores[deck] = {str(k): round(float(max(S[lp - 1, k - 1] for lp in v)), 3)
                        for k, v in m.items()}

        if report:
            best = S.argmax(axis=1)
            mism = []
            for i in range(len(last)):
                if int(best[i]) != i:
                    mism.append({"last": i + 1, "best_today": int(best[i]) + 1,
                                 "score": round(float(S[i, best[i]]), 3),
                                 "same_score": round(float(S[i, i]), 3)
                                 if i < len(today) else None})
            rep[deck] = {"n_last": len(last), "n_today": len(today), "mismatch": mism}
            print(f"   같은 번호가 최고점이 아닌 작년 페이지 {len(mism)}개")

    lec.save_json(lec.lastyear_map, out)
    lec.save_json(lec.work / "lastyear_scores.json", scores)
    print("→ lastyear_map.json (올해 페이지 → 작년 필기 페이지) · lastyear_scores.json (유사도)")
    if report:
        lec.save_json(lec.work / "lastyear_align_report.json", rep)
        print("→ lastyear_align_report.json")


if __name__ == "__main__":
    main()
