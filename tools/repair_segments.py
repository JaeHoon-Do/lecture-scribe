# -*- coding: utf-8 -*-
"""1fps 샘플링·3초 병합 때문에 놓친 '스쳐 지나간 페이지'를 구간 목록에 되살린다.

각 미등장 페이지에 대해 전환 시각 앞뒤를 8fps로 훑어 그 페이지가 화면에 떠 있던
연속 구간을 찾고, 그 구간을 포함하던 기존 세그먼트를 잘라 새 세그먼트로 끼워 넣는다.
결과: _work/segments_final.json (+ 대표 프레임 재저장)
"""
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
import common  # noqa: E402
from match_pages import content_bbox, norm  # noqa: E402

FPS = 8.0


def scan(mp4: Path, t0: float, t1: float):
    cmd = [common.ffmpeg(), "-v", "error", "-ss", str(t0), "-t", str(t1 - t0), "-i", str(mp4),
           "-vf", f"fps={FPS},scale=640:360", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    p = subprocess.run(cmd, capture_output=True)
    fsz = 640 * 360 * 3
    out = []
    for i in range(len(p.stdout) // fsz):
        fr = np.frombuffer(p.stdout[i * fsz:(i + 1) * fsz],
                           dtype=np.uint8).reshape(360, 640, 3)
        out.append((t0 + i / FPS, fr))
    return out


def main():
    lec = common.init()
    m = lec.load_json(lec.segments_matched)
    final = {}

    for deck, d in m.items():
        segs = [dict(s) for s in d["segments"]]
        pdir = lec.pages_dir(deck)
        pv = {}

        def vec(pg):
            if pg not in pv:
                pv[pg] = norm(np.asarray(
                    Image.open(pdir / f"{pg:03d}.jpg").convert("RGB")))
            return pv[pg]

        for pg in sorted(d["missing_pages"]):
            before = [s for s in segs if s["page"] < pg]
            if not before:
                continue
            t_cut = before[-1]["end"]
            win = scan(lec.mp4, t_cut - 6, t_cut + 6)
            target = vec(pg)
            hits = [t for t, fr in win if float(norm(fr) @ target) > 0.90]
            if not hits:
                print(f"  ⚠ {deck} p{pg}: 재탐색 실패 — 건너뜀")
                continue
            a, b = round(min(hits), 2), round(max(hits) + 1 / FPS, 2)

            # 이 시간대를 품고 있는 세그먼트를 잘라낸다
            host = next((s for s in segs if s["start"] <= a < s["end"]), None)
            if host is None:
                print(f"  ⚠ {deck} p{pg}: 포함 세그먼트 없음 ({a}~{b})")
                continue
            new = {"start": a, "end": b, "dur": round(b - a, 2), "page": pg,
                   "score": None, "greedy_page": pg, "greedy_score": None,
                   "frame_t": round((a + b) / 2, 2), "brief": True}
            tail = None
            if b < host["end"] - 0.5 and host["page"] != pg:
                tail = {**host, "start": b, "dur": round(host["end"] - b, 2)}
            host["end"] = a
            host["dur"] = round(a - host["start"], 2)
            i = segs.index(host)
            ins = [new] + ([tail] if tail else [])
            segs[i + 1:i + 1] = ins
            print(f"  {deck} p{pg} 삽입: {a}~{b}s ({new['dur']}s)"
                  + (f", 뒤쪽 p{tail['page']} 재개 {b}s~" if tail else ""))

            # 대표 프레임 저장
            fr = min(win, key=lambda x: abs(x[0] - new["frame_t"]))[1]
            x0, y0, x1, y1 = content_bbox(fr)
            (lec.frames_dir / deck).mkdir(parents=True, exist_ok=True)
            Image.fromarray(fr[y0:y1, x0:x1]).save(
                lec.frames_dir / deck / f"brief_{pg:03d}.jpg", quality=88)

        # 0초 이하 구간 제거 후 번호 재부여
        segs = [s for s in segs if s["dur"] > 0.3]
        for n, s in enumerate(segs, 1):
            s["i"] = n
        pages = [s["page"] for s in segs]
        allp = sorted(int(f.stem) for f in pdir.glob("*.jpg"))
        miss = [p for p in allp if p not in set(pages)]
        mono = all(pages[k] <= pages[k + 1] for k in range(len(pages) - 1))
        final[deck] = {"segments": segs, "missing_pages": miss, "monotone": mono}
        print(f"{deck}: {len(segs)}구간, 미등장 {miss}, 단조 {mono}")

    lec.save_json(lec.segments_final, final)
    print("→ segments_final.json")


if __name__ == "__main__":
    main()
