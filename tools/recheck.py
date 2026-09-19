# -*- coding: utf-8 -*-
"""확신이 낮은 구간을 '다른 조건'으로 다시 전사해 교차검증한다.

같은 오디오라도 조건(문맥 유지 여부·탐색폭·앞뒤 여백)을 바꾸면 결과가 달라진다.
두 번의 결과가 일치하면 신뢰, 갈리면 사람이 판단할 후보로 올린다.
슬라이드 텍스트를 프롬프트에 실어 용어 인식을 돕는 두 번째 조건도 함께 돌린다.

사용법: python recheck.py <키> [logprob임계]   (기본값 lecture.json params.recheck_lp = -0.55)
출력:  _work/recheck_<키>.json  (구간별 1차/2차/3차 결과 비교표)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import common  # noqa: E402

PAD = 2.0


def page_of(t_abs, segs):
    for s in segs:
        if s["start"] <= t_abs < s["end"]:
            return s["page"]
    return None


def main():
    lec = common.init()
    key = sys.argv[1]
    thr = float(sys.argv[2]) if len(sys.argv) > 2 else float(lec.param("recheck_lp", -0.55))

    f = lec.raw(key, "filled")
    if not f.exists():
        f = lec.raw(key)
    tr = lec.load_json(f)
    pages = lec.load_json(lec.segments_final)[key]["segments"]
    slides = {p["page"]: p["text"] for p in lec.load_json(lec.slides_json)[key]["pages"]}

    targets = [s for s in tr["segments"]
               if s["avg_logprob"] < thr or s["no_speech_prob"] > 0.4
               or len(s["text"].strip()) < 4]
    print(f"{key}: 재확인 대상 {len(targets)}개 / 전체 {len(tr['segments'])}")
    if not targets:
        lec.recheck(key).write_text("[]", encoding="utf-8")
        return

    model, dev, _ = common.load_whisper_model()
    lang = common.cfg()["whisper"].get("language", "ko")
    audio = str(lec.audio_wav(key))
    base_prompt = common.build_prompt(lec, key)

    def run(a, b, prompt, ctx):
        segs, _ = model.transcribe(
            audio, language=lang, beam_size=8, best_of=8,
            temperature=[0.0, 0.2, 0.4],
            condition_on_previous_text=ctx, initial_prompt=prompt,
            vad_filter=False, no_speech_threshold=0.9, log_prob_threshold=-2.0,
            clip_timestamps=[max(0.0, a), min(tr["duration"], b)],
        )
        return " ".join(s.text.strip() for s in segs).strip()

    out = []
    for i, s in enumerate(targets, 1):
        a, b = s["start"] - PAD, s["end"] + PAD
        pg = page_of(s["abs_start"], pages)
        st = (slides.get(pg) or "").strip().replace("\n", " ")[:400]
        p2 = base_prompt
        p3 = (f"강의 슬라이드 내용: {st}. " + base_prompt) if st else base_prompt
        v2 = run(a, b, p2, False)
        v3 = run(a, b, p3, True)
        out.append({
            "start": s["start"], "abs": s["abs_start"], "page": pg,
            "lp": s["avg_logprob"], "nsp": s["no_speech_prob"],
            "v1": s["text"], "v2": v2, "v3": v3,
            "agree": (v2 == v3) or (s["text"] in v2 and s["text"] in v3),
        })
        if i % 20 == 0:
            print(f"   … {i}/{len(targets)}", flush=True)

    lec.save_json(lec.recheck(key), out)
    dis = sum(1 for o in out if not o["agree"])
    print(f"{key}: {len(out)}건 재확인, 조건별 결과가 갈린 건 {dis}건 → recheck_{key}.json")


if __name__ == "__main__":
    main()
