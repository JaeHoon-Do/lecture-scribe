# -*- coding: utf-8 -*-
"""녹화 mp4에서 수업별 오디오 wav를 뽑는다 (ffmpeg, 16kHz mono pcm_s16le).

구간은 lecture.json 의 decks[].audio (없으면 video ± default_pad_s).
이 audio.start 가 곧 전사 오프셋이므로, 전사(raw/<key>__full.json)가 이미 있으면
--force 없이는 덮어쓰지 않는다.

사용법: python extract_audio.py [--decks tumor,std] [--force] [--lecture <폴더>]
"""
import subprocess
import sys
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import common  # noqa: E402


def main():
    lec = common.init()
    args = sys.argv[1:]
    force = "--force" in args
    only = None
    if "--decks" in args:
        only = args[args.index("--decks") + 1].split(",")

    a = common.cfg()["audio"]
    lec.audio_dir().mkdir(parents=True, exist_ok=True)
    ok = True
    for d in lec.decks():
        if only and d.key not in only:
            continue
        dst = lec.audio_wav(d.key)
        if dst.exists() and not force:
            print(f"{d.key}: 이미 있음 → 건너뜀 ({dst.name}, --force 로 덮어쓰기)")
            continue
        if lec.raw(d.key).exists() and not force:
            print(f"⚠ {d.key}: 전사본이 이미 있습니다. audio 구간을 바꾸면 fixes 타임스탬프가 어긋납니다. "
                  f"정말 다시 뽑으려면 --force")
            continue
        s, e = d.audio
        cmd = [common.ffmpeg(), "-v", "error", "-y",
               "-ss", str(s), "-to", str(e), "-i", str(lec.mp4),
               "-vn", "-ac", str(a["channels"]), "-ar", str(a["sample_rate"]),
               "-c:a", a["codec"], str(dst)]
        print(f"{d.key}: {common.hms(s)}~{common.hms(e)} ({e - s}s) → {dst.name}")
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            print(f"  ✗ ffmpeg 실패: {r.stderr.strip()[:300]}")
            ok = False
            continue
        with wave.open(str(dst), "rb") as w:
            n, sr, ch, sw = w.getnframes(), w.getframerate(), w.getnchannels(), w.getsampwidth()
        dur = n / sr
        flag = "OK" if (abs(dur - (e - s)) < 0.05 and sr == a["sample_rate"]
                        and ch == a["channels"] and sw == 2) else "⚠ 형식/길이 불일치"
        print(f"  {sr}Hz {ch}ch {sw*8}bit, {n} frames = {dur:.2f}s  [{flag}]")
        if flag != "OK":
            ok = False
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
