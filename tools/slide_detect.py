# -*- coding: utf-8 -*-
"""녹화본에서 슬라이드 전환 시점을 검출한다 (ffmpeg + numpy).

1단계(signal): 1fps 그레이 240x135 프레임을 ffmpeg 파이프로 받아 인접 프레임 차분 신호 계산
       → _work/diff_signal.npy, diff_signal.csv
2단계(segment): 차분 신호에서 전환점을 찾아 슬라이드 구간 목록 생성 → _work/segments.json
       마우스 커서 움직임(수 픽셀)과 슬라이드 전환(화면 대부분)이 규모가 달라 분리된다.
       PowerPoint 하단 툴바가 나타났다 사라지는 영역은 마스킹.
       수업 구간은 lecture.json decks[].video, 임계값은 params.detect_thr(기본 0.06).

사용법: python slide_detect.py signal
        python slide_detect.py segment [임계값]
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import common  # noqa: E402

W, H = 240, 135          # 차분용 저해상
FPS = 1


def signal(lec):
    cmd = [
        common.ffmpeg(), "-v", "error", "-i", str(lec.mp4),
        "-vf", f"fps={FPS},scale={W}:{H},format=gray",
        "-f", "rawvideo", "-pix_fmt", "gray", "-",
    ]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, bufsize=W * H * 32)
    fsz = W * H
    frames = []
    while True:
        buf = p.stdout.read(fsz)
        if len(buf) < fsz:
            break
        frames.append(np.frombuffer(buf, dtype=np.uint8).reshape(H, W))
    p.stdout.close()
    p.wait()
    arr = np.stack(frames).astype(np.int16)
    print(f"프레임 {len(arr)}개 ({len(arr)/60:.1f}분 @{FPS}fps)")

    # PowerPoint 하단 툴바 영역 마스크 (화면 하단 8%)
    mask = np.ones((H, W), dtype=bool)
    mask[int(H * 0.92):, :] = False

    d = np.abs(np.diff(arr, axis=0))                    # (N-1, H, W)
    dm = d[:, mask]
    mad = dm.mean(axis=1)                               # 평균 절대차
    frac = (dm > 24).mean(axis=1)                       # 크게 변한 픽셀 비율

    np.save(lec.diff_signal, np.stack([mad, frac]))
    with open(lec.work / "diff_signal.csv", "w", encoding="utf-8") as f:
        f.write("t,mad,frac\n")
        for i, (a, b) in enumerate(zip(mad, frac)):
            f.write(f"{i+1},{a:.3f},{b:.5f}\n")
    print(f"→ diff_signal.npy / .csv  (mad 중앙값 {np.median(mad):.2f}, "
          f"frac 중앙값 {np.median(frac):.4f})")
    for q in (50, 75, 90, 95, 98, 99, 99.5):
        print(f"   frac {q}분위: {np.percentile(frac, q):.4f}")


def segment(lec, thr: float):
    mad, frac = np.load(lec.diff_signal)
    # frac[i] = 프레임 i와 i+1 사이 변화 → 전환 시각 ≈ i+1초
    cuts = [int(i) + 1 for i, v in enumerate(frac) if v >= thr]

    out = {}
    for key, s, e in lec.lessons():
        pts = [s] + [c for c in cuts if s < c < e] + [e]
        segs, prev = [], pts[0]
        for c in pts[1:]:
            if c - prev >= 3:                 # 3초 미만 구간은 전환 잔상으로 보고 병합
                segs.append([prev, c])
                prev = c
        if prev < e:
            if segs:
                segs[-1][1] = e
            else:
                segs.append([prev, e])
        out[key] = [
            {"i": i, "start": a, "end": b, "dur": b - a, "page": None}
            for i, (a, b) in enumerate(segs, 1)
        ]
        durs = [x["dur"] for x in out[key]]
        print(f"{key}: {len(segs)}구간  (중앙 {np.median(durs):.0f}s, "
              f"최소 {min(durs)}s, 최대 {max(durs)}s)")

    lec.save_json(lec.segments_json, out)
    print("→ segments.json")


if __name__ == "__main__":
    lec = common.init()
    what = sys.argv[1] if len(sys.argv) > 1 else "signal"
    if what == "signal":
        signal(lec)
    else:
        thr = float(sys.argv[2]) if len(sys.argv) > 2 else float(lec.param("detect_thr", 0.06))
        segment(lec, thr)
