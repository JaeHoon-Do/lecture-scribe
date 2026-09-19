# -*- coding: utf-8 -*-
"""gap_check가 '말소리 있음'으로 지목한 구간만 VAD 없이 다시 전사해 채운다.

여백 ±1.2초를 붙여 전사하되, 갭 안에 중심이 들어오는 세그먼트만 채택해
기존 전사본과 겹치는 내용을 중복 삽입하지 않는다.

사용법: python fill_gaps.py <키>
출력:  _work/raw/<키>__filled.json  (전체 전사 + 채운 구간, 시간순 정렬)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import common  # noqa: E402

MARGIN = 1.2

# 침묵 구간을 억지로 전사시키면 whisper가 initial_prompt를 되읊거나
# 학습 데이터의 상투구를 뱉는다(환각). 이런 건 실제 발화가 아니므로 버린다.
# (프롬프트에서 유래하는 문구는 common.prompt_echo_phrases 가 템플릿에서 뽑아 합친다)
_STOCK = (
    "시청해", "구독", "좋아요", "감사합니다", "고맙습니다", "MBC 뉴스",
    "한글자막", "자막 제공", "이 영상은",
)


def _dup_of_neighbor(txt: str, t0: float, t1: float, segs, win: float = 8.0) -> bool:
    """갭 앞뒤로 여백을 두고 다시 전사하다 보면 옆 문장을 다시 받아쓰는 일이 있다.

    whisper의 세그먼트 경계는 정확하지 않아서, 갭에 소리가 남아 있어도 그 소리가
    사실은 옆 문장의 앞뒤 꼬리인 경우가 많다. 이때 재전사본은 옆 문장을 조금 다르게
    받아쓴 것이라 문장 단위 유사도로는 안 잡힌다. 그래서 글자 2-gram이 이웃 문장들에
    얼마나 들어 있는지로 판정한다 — 절반 넘게 겹치면 새 내용이 아니라고 본다.
    """
    from difflib import SequenceMatcher

    a = txt.replace(" ", "")
    if len(a) < 4:
        return True
    near = []
    for s in segs:
        if s["end"] < t0 - win or s["start"] > t1 + win:
            continue
        b = s["text"].replace(" ", "")
        if not b:
            continue
        if SequenceMatcher(None, a, b).ratio() > 0.5:
            return True
        short, long = (a, b) if len(a) <= len(b) else (b, a)
        if len(short) >= 5 and short in long:
            return True
        near.append(b)
    if not near:
        return False
    pool = "".join(near)
    grams = [a[i:i + 2] for i in range(len(a) - 1)]
    if not grams:
        return False
    hit = sum(1 for g in grams if g in pool) / len(grams)
    return hit > 0.5


def _hallucinated(txt: str, prompt: str, blacklist) -> bool:
    t = txt.strip()
    if len(t) < 3:
        return True
    for b in blacklist:
        if b in t:
            return True
    # 프롬프트 문장을 그대로 되풀이한 경우
    for chunk in prompt.split("."):
        c = chunk.strip()
        if len(c) >= 8 and c in t:
            return True
    # 같은 어절이 과도하게 반복되는 경우
    words = t.split()
    if len(words) >= 6 and len(set(words)) <= len(words) / 3:
        return True
    return False


def main():
    lec = common.init()
    key = sys.argv[1]
    gaps = lec.load_json(lec.gaps(key))["need"]
    base = lec.load_json(lec.raw(key))
    dst = lec.raw(key, "filled")
    if not gaps:
        base["segments"] = sorted(base["segments"], key=lambda s: s["start"])
        lec.save_json(dst, base)
        print(f"{key}: 채울 갭 없음")
        return

    model, dev, _ = common.load_whisper_model()
    lang = common.cfg()["whisper"].get("language", "ko")
    audio = str(lec.audio_wav(key))
    prompt = common.build_prompt(lec, key)
    blacklist = tuple(common.prompt_echo_phrases(lec)) + _STOCK
    off = lec.offset(key)
    added = []
    for g in gaps:
        a = max(0.0, g["start"] - MARGIN)
        b = min(base["duration"], g["end"] + MARGIN)
        segs, _ = model.transcribe(
            audio, language=lang, beam_size=5, best_of=5,
            temperature=[0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
            word_timestamps=True, condition_on_previous_text=False,
            initial_prompt=prompt, vad_filter=False,
            no_speech_threshold=0.9, log_prob_threshold=-1.5,
            clip_timestamps=[a, b],
        )
        for s in segs:
            mid = (s.start + s.end) / 2
            if not (g["start"] - 0.35 <= mid <= g["end"] + 0.35):
                continue
            txt = s.text.strip()
            if _hallucinated(txt, prompt, blacklist):
                print(f"  -[{s.start:7.2f}~{s.end:7.2f}] 환각으로 판단해 버림: {txt[:60]}")
                continue
            if _dup_of_neighbor(txt, s.start, s.end, base["segments"]):
                print(f"  -[{s.start:7.2f}~{s.end:7.2f}] 옆 문장과 중복이라 버림: {txt[:60]}")
                continue
            added.append({
                "id": -1, "start": round(s.start, 2), "end": round(s.end, 2),
                "abs_start": round(s.start + off, 2),
                "abs_end": round(s.end + off, 2),
                "text": txt,
                "avg_logprob": round(s.avg_logprob, 3),
                "no_speech_prob": round(s.no_speech_prob, 3),
                "compression_ratio": round(s.compression_ratio, 2),
                "filled": True,
                "words": [{"w": w.word, "s": round(w.start, 2), "e": round(w.end, 2),
                           "p": round(w.probability, 2)} for w in (s.words or [])],
            })
            print(f"  +[{s.start:7.2f}~{s.end:7.2f}] {txt}")

    allsegs = sorted(base["segments"] + added, key=lambda s: s["start"])
    for i, s in enumerate(allsegs, 1):
        s["id"] = i
    base["segments"] = allsegs
    base["filled_count"] = len(added)
    lec.save_json(dst, base)
    print(f"{key}: {len(added)}개 세그먼트 보충 → {dst.name}")


if __name__ == "__main__":
    main()
