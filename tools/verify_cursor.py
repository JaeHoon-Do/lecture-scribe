# -*- coding: utf-8 -*-
"""dwell 검출 결과를 프레임 위에 그려 눈으로 검증한다.
사용법: python verify_cursor.py <deck> <seg번호…>   → _work/verify/<deck>_segNNN_pN.png
"""
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).parent))
import common  # noqa: E402


def frame_at(mp4: Path, t):
    cmd = [common.ffmpeg(), "-v", "error", "-ss", str(t), "-i", str(mp4),
           "-frames:v", "1", "-vf", "scale=640:360", "-f", "rawvideo",
           "-pix_fmt", "rgb24", "-"]
    raw = subprocess.run(cmd, capture_output=True).stdout
    return np.frombuffer(raw[:640 * 360 * 3], dtype=np.uint8).reshape(360, 640, 3)


def main():
    lec = common.init()
    deck = sys.argv[1]
    want = [int(x) for x in sys.argv[2:]]
    out = lec.verify_dir
    out.mkdir(exist_ok=True)
    cur = lec.load_json(lec.cursor(deck))[deck]
    for r in cur["segments"]:
        if r["seg"] not in want:
            continue
        if not r["dwells"]:
            print(f"seg{r['seg']}: dwell 없음")
            continue
        t = r["dwells"][len(r["dwells"]) // 2]["t0"]
        im = Image.fromarray(frame_at(lec.mp4, t)).convert("RGB").resize((1280, 720))
        d = ImageDraw.Draw(im)
        for k, dw in enumerate(r["dwells"], 1):
            x, y = dw["x"] * 2, dw["y"] * 2
            d.ellipse([x - 20, y - 20, x + 20, y + 20], outline=(255, 0, 0), width=3)
            d.text((x + 23, y - 8), f"{k} ({dw['dur']}s)", fill=(255, 0, 0))
        f = out / f"{deck}_seg{r['seg']:03d}_p{r['page']}.png"
        im.save(f)
        print(f"seg{r['seg']} p{r['page']}: dwell {len(r['dwells'])}개 (프레임 t={t}) → {f.name}")


if __name__ == "__main__":
    main()
