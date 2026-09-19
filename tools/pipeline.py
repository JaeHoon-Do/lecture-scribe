# -*- coding: utf-8 -*-
"""와벨헬퍼 파이프라인 드라이버 — 단계를 순서대로 돌린다.

사용법 (와벨헬퍼 폴더의 wabel.cmd 로 호출):
  wabel --lecture <강의폴더> [단계…] [--from 단계] [--to 단계] [--only 단계] [--decks a,b] [--dry-run]
  wabel --lecture <강의폴더> merge <key> [--force]      notes 조각 합치기(명시 실행만)
  wabel stages                                          단계 목록

단계(순서):
  audio       extract_audio.py            mp4 → _work/audio/<key>.wav
  slides      extract_slides.py           pdf 텍스트 → slides.json
  pages       render_pages.py all         pdf 렌더 → pages/ · output/_slides/ · lastyear/
  transcribe  transcribe.py <key>         whisper (GPU, 짧은 덱부터)
  detect      slide_detect.py signal/segment
  match       match_pages.py ; check_skipped.py(보고만)
  repair      repair_segments.py
  cursor      cursor_track.py <key>
  lastyear    lastyear_map.py
  post        키별 gap_check → fill_gaps → recheck → assemble → dump_bundle
  ── 여기서 Claude가 notes_<key>.json 작성, verify_shots/apply_verify ──
  build       키별 make_script_md · make_html · make_html --tablet · make_pdf · make_writeup ; make_index
  verify      verify_final.py

인자 없이 실행하면 audio~post 까지(자동 구간) 돌린다. 각 단계 출력은 _work/logs/ 에도 남긴다.
"""
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import common  # noqa: E402

TOOLS = Path(__file__).parent

STAGES = ["audio", "slides", "pages", "transcribe", "detect", "match", "repair",
          "cursor", "lastyear", "post", "build", "verify"]
AUTO_TO = "post"


def _t(name, *args):
    return [str(TOOLS / name), *map(str, args)]


def commands(stage, lec, keys):
    """단계 → [명령(스크립트 인자 목록)]"""
    by_len = sorted(keys, key=lambda k: lec.deck(k).audio[1] - lec.deck(k).audio[0])
    if stage == "audio":
        return [_t("extract_audio.py", "--decks", ",".join(keys))]
    if stage == "slides":
        return [_t("extract_slides.py")]
    if stage == "pages":
        return [_t("render_pages.py", "all")]
    if stage == "transcribe":
        return [_t("transcribe.py", k) for k in by_len]
    if stage == "detect":
        return [_t("slide_detect.py", "signal"), _t("slide_detect.py", "segment")]
    if stage == "match":
        return [_t("match_pages.py"), _t("check_skipped.py")]
    if stage == "repair":
        return [_t("repair_segments.py")]
    if stage == "cursor":
        return [_t("cursor_track.py", k) for k in keys]
    if stage == "lastyear":
        return [_t("lastyear_map.py")]
    if stage == "post":
        out = []
        for k in by_len:
            out += [_t("gap_check.py", k), _t("fill_gaps.py", k), _t("recheck.py", k),
                    _t("assemble.py", k), _t("dump_bundle.py", k)]
        return out
    if stage == "build":
        out = []
        for k in keys:
            out += [_t("make_script_md.py", k), _t("make_html.py", k),
                    _t("make_html.py", k, "--tablet"), _t("make_pdf.py", k),
                    _t("make_writeup.py", k)]
        out.append(_t("make_index.py"))
        return out
    if stage == "verify":
        return [_t("verify_final.py")]
    raise KeyError(stage)


def run(cmd, lec, extra, dry, log):
    full = [common.python_exe(), *cmd, "--lecture", str(lec.root), *extra]
    shown = " ".join(f'"{a}"' if " " in a else a for a in full)
    print(f"\n$ {shown}", flush=True)
    if dry:
        return 0
    log.write(f"\n$ {shown}\n")
    log.flush()
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    p = subprocess.Popen(full, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, encoding="utf-8", errors="replace", env=env,
                         cwd=str(lec.root))
    for line in p.stdout:
        sys.stdout.write(line)
        sys.stdout.flush()
        log.write(line)
    p.wait()
    log.flush()
    return p.returncode


def main():
    argv = sys.argv[1:]
    if argv[:1] == ["stages"]:
        print("\n".join(STAGES))
        return
    dry = "--dry-run" in argv
    argv = [a for a in argv if a != "--dry-run"]

    lec = common.init(argv)          # --lecture/--out 제거
    extra = ["--out", str(lec.out)] if lec.out != lec.root / lec.data.get("output_dir", "output") else []

    # merge <key> [--force]
    if argv[:1] == ["merge"]:
        cmd = _t("merge_notes.py", *argv[1:])
        lec.logs_dir.mkdir(parents=True, exist_ok=True)
        with open(lec.logs_dir / "merge.log", "a", encoding="utf-8") as log:
            sys.exit(run(cmd, lec, extra, dry, log))

    def pop(name):
        if name in argv:
            i = argv.index(name)
            v = argv[i + 1]
            del argv[i:i + 2]
            return v
        return None

    frm, to, only, decks = pop("--from"), pop("--to"), pop("--only"), pop("--decks")
    keys = decks.split(",") if decks else lec.keys()
    for k in keys:
        lec.deck(k)

    named = [a for a in argv if not a.startswith("--")]
    bad = [a for a in named if a not in STAGES]
    if bad:
        sys.exit(f"모르는 단계: {bad}\n단계: {STAGES}")
    if only:
        sel = [only]
    elif named:
        sel = named
    else:
        a = STAGES.index(frm) if frm else 0
        b = STAGES.index(to) if to else STAGES.index(AUTO_TO)
        sel = STAGES[a:b + 1]

    print(f"강의: {lec.root.name}\n덱: {keys}\n단계: {sel}{'  (dry-run)' if dry else ''}")
    lec.logs_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%y%m%d_%H%M%S")
    for st in sel:
        t0 = time.time()
        print(f"\n{'='*20} [{st}] {'='*20}", flush=True)
        with open(lec.logs_dir / f"{st}_{stamp}.log", "a", encoding="utf-8") as log:
            for cmd in commands(st, lec, keys):
                rc = run(cmd, lec, extra, dry, log)
                if rc != 0:
                    print(f"\n✗ [{st}] 실패 (exit {rc}): {Path(cmd[0]).name} {' '.join(cmd[1:])}"
                          f"\n  로그: {log.name}")
                    sys.exit(rc)
        print(f"[{st}] 완료 {time.time() - t0:.0f}s")
    print("\n✅ 끝:", ", ".join(sel))


if __name__ == "__main__":
    # config.json 의 python 이 아니면 그것으로 다시 실행 (본체 venv 통일)
    want = common.python_exe()
    if Path(want).exists() and Path(sys.executable).resolve() != Path(want).resolve():
        os.execv(want, [want, *sys.argv])
    main()
