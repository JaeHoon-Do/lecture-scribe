# -*- coding: utf-8 -*-
"""수업별 오디오를 faster-whisper로 전사한다 (모델·장치는 config.json whisper).

무누락이 최우선이라:
  - word_timestamps=True 로 단어 단위 시각 확보 (마우스 포인팅 정렬용)
  - segment별 avg_logprob / no_speech_prob 저장 → 저확신 구간 사후 교정 대상
  - VAD는 관대한 설정(긴 침묵만 제거)으로 환각 억제, 이후 gap 검사로 누락 확인
  - condition_on_previous_text=False → 긴 오디오에서 반복 환각 전파 방지

사용법: python transcribe.py <키>              (예: tumor)
        python transcribe.py <키> --gap A B    (A~B초 구간만 VAD 없이 재전사)
        python transcribe.py --check           (모델 로드만 해보고 종료)
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import common  # noqa: E402


def transcribe(lec, key: str, gap: tuple | None = None):
    model, dev, name = common.load_whisper_model()
    w = common.cfg()["whisper"]

    audio = lec.audio_wav(key)
    if not audio.exists():
        sys.exit(f"오디오가 없습니다: {audio}  (extract_audio.py 먼저)")
    prompt = common.build_prompt(lec, key)
    print(f"🎙 {key} 전사 시작 ({name}, {dev})\n   prompt: {prompt[:160]}…", file=sys.stderr)

    kw = dict(
        language=w.get("language", "ko"),
        beam_size=5,
        best_of=5,
        temperature=[0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
        word_timestamps=True,
        condition_on_previous_text=False,
        initial_prompt=prompt,
        compression_ratio_threshold=2.4,
        log_prob_threshold=-1.0,
        no_speech_threshold=0.6,
    )
    if gap:
        kw["clip_timestamps"] = [float(gap[0]), float(gap[1])]
        kw["vad_filter"] = False
        tag = f"gap_{int(float(gap[0]))}_{int(float(gap[1]))}"
    else:
        kw["vad_filter"] = True
        kw["vad_parameters"] = dict(w["vad"])
        tag = "full"

    segs, info = model.transcribe(str(audio), **kw)
    off = lec.offset(key)

    out, n = [], 0
    for s in segs:
        n += 1
        out.append({
            "id": s.id,
            "start": round(s.start, 2),
            "end": round(s.end, 2),
            "abs_start": round(s.start + off, 2),
            "abs_end": round(s.end + off, 2),
            "text": s.text.strip(),
            "avg_logprob": round(s.avg_logprob, 3),
            "no_speech_prob": round(s.no_speech_prob, 3),
            "compression_ratio": round(s.compression_ratio, 2),
            "words": [
                {"w": w_.word, "s": round(w_.start, 2), "e": round(w_.end, 2),
                 "p": round(w_.probability, 2)}
                for w_ in (s.words or [])
            ],
        })
        if n % 50 == 0:
            print(f"   … {n}세그먼트 / {s.end/60:.1f}분", file=sys.stderr, flush=True)

    res = {
        "key": key, "tag": tag, "device": dev, "model": name,
        "offset": off, "duration": round(info.duration, 1),
        "prompt": prompt, "segments": out,
    }
    dst = lec.raw(key, tag)
    lec.save_json(dst, res)
    print(f"✅ {key}/{tag}: {len(out)}세그먼트 → {dst.name}", file=sys.stderr)


if __name__ == "__main__":
    lec = common.init()
    if "--check" in sys.argv:
        model, dev, name = common.load_whisper_model()
        print(f"모델 로드 OK: {name} ({dev})")
        sys.exit(0)
    if len(sys.argv) < 2:
        sys.exit("사용법: python transcribe.py <키> [--gap A B] | --check")
    k = sys.argv[1]
    g = None
    if "--gap" in sys.argv:
        i = sys.argv.index("--gap")
        g = (sys.argv[i + 1], sys.argv[i + 2])
    transcribe(lec, k, g)
