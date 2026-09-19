# -*- coding: utf-8 -*-
"""매칭에서 '미등장'으로 나온 페이지가 정말 건너뛴 것인지, 아니면 1fps 샘플링·
3초 병합 규칙 때문에 놓친 것인지 확인한다. 전환 시각 앞뒤를 0.25초 간격으로 다시 훑어
해당 페이지와의 유사도가 튀는 지점이 있는지 본다. (보고만 하고 파일은 안 만든다)
"""
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
import common  # noqa: E402
from match_pages import norm  # noqa: E402


def frames_window(mp4: Path, t0: float, t1: float, fps: float = 4.0):
    cmd = [common.ffmpeg(), "-v", "error", "-ss", str(t0), "-t", str(t1 - t0), "-i", str(mp4),
           "-vf", f"fps={fps},scale=640:360", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    p = subprocess.run(cmd, capture_output=True)
    fsz = 640 * 360 * 3
    n = len(p.stdout) // fsz
    for i in range(n):
        yield t0 + i / fps, np.frombuffer(
            p.stdout[i * fsz:(i + 1) * fsz], dtype=np.uint8).reshape(360, 640, 3)


def main():
    lec = common.init()
    m = lec.load_json(lec.segments_matched)
    for deck, d in m.items():
        miss = d["missing_pages"]
        if not miss:
            continue
        segs = d["segments"]
        for pg in miss:
            # 건너뛴 페이지의 앞 페이지가 끝나는 시각 = 의심 구간
            before = [s for s in segs if s["page"] < pg]
            after = [s for s in segs if s["page"] > pg]
            if not before or not after:
                print(f"{deck} p{pg}: 앞뒤 구간 없음")
                continue
            t_cut = before[-1]["end"]
            pv = norm(np.asarray(
                Image.open(lec.pages_dir(deck) / f"{pg:03d}.jpg").convert("RGB")))
            best = (-1, None)
            for t, fr in frames_window(lec.mp4, t_cut - 4, t_cut + 4, 4.0):
                s = float(norm(fr) @ pv)
                if s > best[0]:
                    best = (s, t)
            print(f"{deck} p{pg}: 전환시각 {t_cut}s 부근 최고 유사도 "
                  f"{best[0]:.3f} @ {best[1]:.2f}s "
                  f"→ {'스쳐 지나감(놓침)' if best[0] > 0.75 else '실제로 건너뜀'}")


if __name__ == "__main__":
    main()
