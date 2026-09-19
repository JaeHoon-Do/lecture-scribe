# -*- coding: utf-8 -*-
"""교수님 마우스 포인터의 위치·머문 지점(dwell)을 추적한다 (ffmpeg + numpy).

원리: 한 슬라이드가 떠 있는 동안 화면에서 움직이는 것은 커서뿐이다.
      구간을 60초 청크로 나눠 청크별 중앙값 배경을 만들고, 각 프레임에서 배경과
      다른 지점을 찾으면 그게 커서다. 같은 자리에 일정 시간 머물면 dwell 이벤트로 본다.
      (PowerPoint 하단 툴바·슬라이드 번호 영역은 마스킹)

출력: _work/cursor_<deck>.json
      { deck: {bbox, segments:[ {seg, page, dwells:[{t0,t1,dur,x,y,nx,ny}], track:[[t,x,y],…] } ]} }
      nx,ny = 슬라이드 영역 기준 0~1 정규화 좌표 (PDF 위 표시에 그대로 사용)
사용법: python cursor_track.py <deck>
"""
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import common  # noqa: E402
from match_pages import content_bbox  # noqa: E402

FW, FH = 640, 360        # 처리 해상도 (원본 1280x720의 1/2)
FPS = 5.0
CHUNK = 60.0             # 배경 추정 청크 길이(초)
BOX = 7                  # 커서 크기에 맞춘 박스 필터 한 변
PEAK_MIN = 14.0          # 커서로 인정할 최소 응답
DWELL_R = 14             # 같은 자리로 볼 반경(px @640x360)
DWELL_MIN = 0.8          # 최소 체류 시간(초)

_MP4 = None


def stream(t0: float, t1: float):
    cmd = [common.ffmpeg(), "-v", "error", "-ss", f"{t0:.3f}", "-t", f"{t1-t0:.3f}",
           "-i", str(_MP4), "-vf", f"fps={FPS},scale={FW}:{FH},format=gray",
           "-f", "rawvideo", "-pix_fmt", "gray", "-"]
    p = subprocess.run(cmd, capture_output=True)
    fsz = FW * FH
    n = len(p.stdout) // fsz
    return np.frombuffer(p.stdout[:n * fsz], dtype=np.uint8).reshape(n, FH, FW)


def boxsum(a: np.ndarray, k: int) -> np.ndarray:
    """k x k 합 (적분영상). 반환 크기는 입력과 동일(유효 영역 밖은 0)."""
    ii = np.zeros((a.shape[0] + 1, a.shape[1] + 1), dtype=np.float32)
    ii[1:, 1:] = a.cumsum(0).cumsum(1)
    H, W = a.shape
    out = np.zeros_like(a, dtype=np.float32)
    out[:H - k + 1, :W - k + 1] = (
        ii[k:, k:] - ii[:H - k + 1, k:] - ii[k:, :W - k + 1] + ii[:H - k + 1, :W - k + 1]
    )
    return out / (k * k)


def track_segment(t0: float, t1: float, bbox: tuple):
    """구간의 프레임별 커서 좌표를 구한다. bbox = 슬라이드 영역(640x360 기준)."""
    pts = []
    x0, y0, x1, y1 = bbox
    t = t0
    while t < t1 - 0.05:
        te = min(t + CHUNK, t1)
        fr = stream(t, te)
        if len(fr) < 3:
            t = te
            continue
        f = fr.astype(np.float32)
        bg = np.median(f, axis=0)
        for i in range(len(f)):
            d = np.abs(f[i] - bg)
            # 슬라이드 영역 밖 + 하단 툴바/상태표시줄 마스킹
            m = np.zeros_like(d)
            yb = int(y1 - (y1 - y0) * 0.05)          # 하단 5% 제외
            m[y0:yb, x0:x1] = d[y0:yb, x0:x1]
            r = boxsum(m, BOX)
            idx = int(r.argmax())
            py, px = divmod(idx, FW)
            peak = float(r[py, px])
            if peak >= PEAK_MIN:
                pts.append((round(t + i / FPS, 2), px + BOX // 2, py + BOX // 2,
                            round(peak, 1)))
        t = te
    return pts


def dwells(pts: list, bbox: tuple):
    """연속 프레임에서 같은 자리에 머문 구간을 묶는다."""
    x0, y0, x1, y1 = bbox
    out, cur = [], []
    for p in pts:
        if not cur:
            cur = [p]
            continue
        gap = p[0] - cur[-1][0]
        cx = np.mean([q[1] for q in cur]); cy = np.mean([q[2] for q in cur])
        if gap <= 1.0 / FPS + 0.35 and abs(p[1] - cx) <= DWELL_R and abs(p[2] - cy) <= DWELL_R:
            cur.append(p)
        else:
            if cur[-1][0] - cur[0][0] >= DWELL_MIN:
                out.append(cur)
            cur = [p]
    if cur and cur[-1][0] - cur[0][0] >= DWELL_MIN:
        out.append(cur)

    res = []
    for c in out:
        mx = float(np.median([q[1] for q in c])); my = float(np.median([q[2] for q in c]))
        res.append({
            "t0": c[0][0], "t1": c[-1][0], "dur": round(c[-1][0] - c[0][0], 2),
            "x": round(mx, 1), "y": round(my, 1),
            "nx": round((mx - x0) / max(x1 - x0, 1), 4),
            "ny": round((my - y0) / max(y1 - y0, 1), 4),
            "n": len(c),
        })
    return res


def main():
    global _MP4
    lec = common.init()
    _MP4 = lec.mp4
    only = sys.argv[1] if len(sys.argv) > 1 else None
    segs = lec.load_json(lec.segments_final)

    out = {}
    for deck, d in segs.items():
        if only and deck != only:
            continue
        # 슬라이드 표시 영역은 강의 내내 고정 — 중간 프레임에서 한 번만 구한다
        mid = d["segments"][len(d["segments"]) // 2]
        cmd = [common.ffmpeg(), "-v", "error", "-ss", str(mid["frame_t"]), "-i", str(_MP4),
               "-frames:v", "1", "-vf", f"scale={FW}:{FH}", "-f", "rawvideo",
               "-pix_fmt", "rgb24", "-"]
        raw = subprocess.run(cmd, capture_output=True).stdout
        fr = np.frombuffer(raw[:FW * FH * 3], dtype=np.uint8).reshape(FH, FW, 3)
        bbox = content_bbox(fr)
        print(f"{deck}: 슬라이드 영역 {bbox}")

        rows = []
        for k, s in enumerate(d["segments"], 1):
            if s["dur"] < 1.5:
                rows.append({"seg": s["i"], "page": s["page"], "dwells": [], "track": []})
                continue
            pts = track_segment(s["start"] + 0.6, s["end"] - 0.2, bbox)
            dw = dwells(pts, bbox)
            rows.append({
                "seg": s["i"], "page": s["page"],
                "start": s["start"], "end": s["end"],
                "dwells": dw,
                "track": [[p[0], p[1], p[2]] for p in pts],
            })
            if k % 20 == 0:
                print(f"   … {k}/{len(d['segments'])}구간", flush=True)
        nd = sum(len(r["dwells"]) for r in rows)
        print(f"{deck}: dwell {nd}개 / {len(rows)}구간")
        out[deck] = {"bbox": list(bbox), "segments": rows}

    dst = lec.cursor(only) if only else lec.work / "cursor.json"
    dst.write_text(__import__("json").dumps(out, ensure_ascii=False), encoding="utf-8")
    print("→", dst.name)


if __name__ == "__main__":
    main()
