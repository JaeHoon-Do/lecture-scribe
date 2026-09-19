# -*- coding: utf-8 -*-
"""슬라이드 구간 ↔ PDF 페이지 매칭 (ffmpeg + numpy + pillow).

각 구간의 대표 프레임을 뽑아 렌더된 PDF 페이지와 이미지 유사도로 대조하고,
'강의는 앞으로 진행한다'는 사전지식을 DP(단조 정렬)로 반영해 페이지를 확정한다.
단순 최고점 매칭과 DP 결과가 다른 구간은 confirm 목록에 담아 사람이 눈으로 확인.

출력: _work/segments_matched.json, _work/frames/seg/<deck>/<i>.jpg(대표 프레임)
사용법: python match_pages.py
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
import common  # noqa: E402

VW, VH = 640, 360          # 스트리밍 해상도(전체 화면)
CW, CH = 128, 96           # 비교용 해상도


def content_bbox(img: np.ndarray) -> tuple:
    """레터박스(검은 여백)를 제외한 슬라이드 영역 bbox를 찾는다."""
    g = img.mean(axis=2)
    col = g.mean(axis=0)
    row = g.mean(axis=1)
    cs = np.where(col > 12)[0]
    rs = np.where(row > 12)[0]
    if len(cs) < 10 or len(rs) < 10:
        return 0, 0, img.shape[1], img.shape[0]
    return int(cs[0]), int(rs[0]), int(cs[-1]) + 1, int(rs[-1]) + 1


def norm(img: np.ndarray) -> np.ndarray:
    """비교용 정규화 벡터: 슬라이드 영역만 잘라 CWxCH로 축소 후 표준화."""
    x0, y0, x1, y1 = content_bbox(img)
    crop = Image.fromarray(img[y0:y1, x0:x1]).resize((CW, CH), Image.BILINEAR)
    v = np.asarray(crop, dtype=np.float32).ravel()
    v -= v.mean()
    n = np.linalg.norm(v)
    return v / n if n > 1e-6 else v


def grab_frames(mp4: Path, times: list[int]) -> dict:
    """지정한 초(영상 절대시각)의 프레임을 1fps 스트림에서 뽑는다."""
    want = set(times)
    cmd = [common.ffmpeg(), "-v", "error", "-i", str(mp4),
           "-vf", f"fps=1,scale={VW}:{VH}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, bufsize=VW * VH * 3 * 8)
    fsz = VW * VH * 3
    got, idx = {}, 0
    while True:
        buf = p.stdout.read(fsz)
        if len(buf) < fsz:
            break
        if idx in want:
            got[idx] = np.frombuffer(buf, dtype=np.uint8).reshape(VH, VW, 3).copy()
        idx += 1
    p.stdout.close(); p.wait()
    print(f"  프레임 수집: {len(got)}/{len(want)}")
    return got


def page_vectors(pages_dir: Path) -> tuple:
    files = sorted(pages_dir.glob("*.jpg"))
    if not files:
        sys.exit(f"페이지 렌더가 없습니다: {pages_dir}  (render_pages.py match 먼저)")
    vecs = []
    for f in files:
        im = np.asarray(Image.open(f).convert("RGB"))
        vecs.append(norm(im))
    return np.stack(vecs), [int(f.stem) for f in files]


def dp_align(S: np.ndarray) -> list:
    """단조 비감소 페이지 배정으로 총점 최대화 (구간 i → 페이지 j)."""
    N, P = S.shape
    best = np.full((N, P), -1e9, dtype=np.float64)
    back = np.zeros((N, P), dtype=np.int32)
    best[0] = S[0]
    for i in range(1, N):
        run, arg = -1e9, 0
        for j in range(P):
            if best[i - 1, j] > run:
                run, arg = best[i - 1, j], j
            best[i, j] = S[i, j] + run
            back[i, j] = arg
    j = int(np.argmax(best[N - 1]))
    path = [j]
    for i in range(N - 1, 0, -1):
        j = int(back[i, j])
        path.append(j)
    return path[::-1]


def main():
    lec = common.init()
    segs = lec.load_json(lec.segments_json)

    # 대표 프레임 시각: 구간 시작 +2초(전환 잔상 회피), 짧으면 중간
    picks = {}
    for deck, lst in segs.items():
        for s in lst:
            t = s["start"] + 2 if s["dur"] >= 5 else s["start"] + s["dur"] // 2
            picks[(deck, s["i"])] = min(t, s["end"] - 1)

    frames = grab_frames(lec.mp4, sorted(set(picks.values())))

    result = {}
    for deck, lst in segs.items():
        PV, pnums = page_vectors(lec.pages_dir(deck))
        SEG = lec.frames_dir / deck
        SEG.mkdir(parents=True, exist_ok=True)

        vecs = []
        for s in lst:
            t = picks[(deck, s["i"])]
            fr = frames.get(t)
            if fr is None:
                vecs.append(np.zeros(CW * CH * 3, dtype=np.float32))
                continue
            x0, y0, x1, y1 = content_bbox(fr)
            Image.fromarray(fr[y0:y1, x0:x1]).save(SEG / f"{s['i']:03d}.jpg", quality=88)
            vecs.append(norm(fr))
        SV = np.stack(vecs)

        S = SV @ PV.T                        # (구간, 페이지) 코사인 유사도
        greedy = S.argmax(axis=1)
        path = dp_align(S)

        out, confirm = [], []
        for k, s in enumerate(lst):
            pg = pnums[path[k]]
            gp = pnums[greedy[k]]
            rec = dict(s)
            rec.update({
                "page": pg,
                "score": round(float(S[k, path[k]]), 4),
                "greedy_page": gp,
                "greedy_score": round(float(S[k, greedy[k]]), 4),
                "frame_t": picks[(deck, s["i"])],
            })
            out.append(rec)
            if pg != gp or rec["score"] < 0.80:
                confirm.append(rec["i"])

        used = sorted({r["page"] for r in out})
        missing = [p for p in pnums if p not in used]
        result[deck] = {"segments": out, "confirm": confirm, "missing_pages": missing}
        print(f"{deck}: {len(out)}구간 → 페이지 {len(used)}/{len(pnums)}종 사용, "
              f"확인필요 {len(confirm)}건, 미등장 페이지 {len(missing)}개")
        if missing:
            print(f"   미등장: {missing}")

    lec.save_json(lec.segments_matched, result)
    print("→ segments_matched.json")


if __name__ == "__main__":
    main()
