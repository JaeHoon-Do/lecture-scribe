# -*- coding: utf-8 -*-
"""전사본의 누락(갭)을 찾는다 — '하나도 빠짐없이'를 기계적으로 보증하기 위한 단계.

세그먼트 사이의 빈 시간을 모두 뽑아, 그 구간 오디오의 실제 음량(RMS)을 재서
  - 조용함  → 강의 중 침묵(슬라이드 넘기는 시간 등). 누락 아님.
  - 소리 있음 → whisper가 놓쳤을 가능성. 재전사 대상.
으로 가른다.

사용법: python gap_check.py <키> [최소갭초]   (기본값 lecture.json params.gap_min_s = 2.0)
출력:  _work/gaps_<키>.json  (재전사 대상 목록)
"""
import sys
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import common  # noqa: E402


def load_audio(path: Path):
    with wave.open(str(path), "rb") as w:
        sr = w.getframerate()
        a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    return a.astype(np.float32) / 32768.0, sr


def main():
    lec = common.init()
    key = sys.argv[1]
    min_gap = float(sys.argv[2]) if len(sys.argv) > 2 else float(lec.param("gap_min_s", 2.0))

    data = lec.load_json(lec.raw(key))
    segs = data["segments"]
    dur = data["duration"]
    a, sr = load_audio(lec.audio_wav(key))

    # 전체 음량 분포로 '조용함' 기준을 잡는다 (강의 자체의 잡음 수준에 맞춤)
    win = int(sr * 0.1)
    n = len(a) // win
    rms_all = np.sqrt((a[:n * win].reshape(n, win) ** 2).mean(axis=1))
    quiet = float(np.percentile(rms_all, 20)) * 2.5

    gaps = []
    prev = 0.0
    bounds = [(s["start"], s["end"]) for s in segs]
    for s, e in bounds + [(dur, dur)]:
        if s - prev >= min_gap:
            i0, i1 = int(prev * sr), int(min(s, dur) * sr)
            seg = a[i0:i1]
            if len(seg) < win:
                prev = max(prev, e)
                continue
            m = len(seg) // win
            r = np.sqrt((seg[:m * win].reshape(m, win) ** 2).mean(axis=1))
            loud = float((r > quiet).mean())
            peak = float(r.max())
            gaps.append({
                "start": round(prev, 2), "end": round(s, 2),
                "dur": round(s - prev, 2),
                "loud_frac": round(loud, 3), "peak_rms": round(peak, 4),
                "speech": bool(loud > 0.25 and peak > quiet * 1.5),
            })
        prev = max(prev, e)

    need = [g for g in gaps if g["speech"]]
    tot_gap = sum(g["dur"] for g in gaps)
    tot_need = sum(g["dur"] for g in need)
    covered = sum(min(e, dur) - s for s, e in bounds)
    print(f"{key}: 길이 {dur:.0f}s / 전사 커버 {covered:.0f}s ({covered/dur*100:.1f}%)")
    print(f"  갭 {len(gaps)}개 {tot_gap:.0f}s (조용함 기준 rms>{quiet:.4f})")
    print(f"  → 재전사 필요 {len(need)}개 {tot_need:.0f}s")
    for g in need[:40]:
        print(f"     {g['start']:8.2f}~{g['end']:8.2f} ({g['dur']:5.2f}s) "
              f"loud={g['loud_frac']:.2f} peak={g['peak_rms']:.4f}")

    lec.save_json(lec.gaps(key), {"key": key, "quiet_thr": quiet, "gaps": gaps, "need": need})
    print(f"→ gaps_{key}.json")


if __name__ == "__main__":
    main()
