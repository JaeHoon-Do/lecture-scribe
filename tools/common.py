# -*- coding: utf-8 -*-
"""와벨헬퍼 공통 모듈 — 강의 폴더 찾기, lecture.json / config.json 접근자.

모든 스크립트는 첫 줄에서
    lec = common.init()
를 호출한다. init()은 sys.argv에서 --lecture <경로> / --out <경로> 를 떼어내므로
그 뒤의 positional 인자(<key>, all, signal …)는 기존과 똑같이 sys.argv[1:]로 쓴다.

강의 폴더 결정 순서:
  1. --lecture <경로>
  2. 환경변수 WABEL_LECTURE
  3. 현재 디렉터리에서 부모로 올라가며 lecture.json 이 있는 첫 폴더
  4. 실패 → 와벨헬퍼 아래 lecture.json 을 가진 폴더 목록을 보여주고 종료
"""
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # repo root
TOOLS = ROOT / "tools"

_CFG = None
_LEC = None


# ─────────────────────────── config.json ───────────────────────────
def cfg() -> dict:
    global _CFG
    if _CFG is None:
        _CFG = json.loads((ROOT / "config.json").read_text(encoding="utf-8-sig"))
    return _CFG


def python_exe() -> str:
    return cfg().get("python") or sys.executable


def ffmpeg() -> str:
    return cfg().get("ffmpeg", "ffmpeg")


def fonts() -> tuple[str, str]:
    f = cfg()["fonts"]
    for p in (f["regular"], f["bold"]):
        if not Path(p).exists():
            sys.exit(f"폰트가 없습니다: {p}  (config.json fonts 확인)")
    return f["regular"], f["bold"]


def render_cfg(name: str) -> tuple[int, int]:
    r = cfg()["render"][name]
    return int(r["width"]), int(r["quality"])


# ─────────────────────────── 시간 유틸 ───────────────────────────
def sec(s) -> int:
    """'HH:MM:SS' | 'MM:SS' | 숫자 → 정수 초"""
    if isinstance(s, (int, float)):
        return int(s)
    parts = [int(x) for x in str(s).strip().split(":")]
    while len(parts) < 3:
        parts.insert(0, 0)
    h, m, x = parts
    return h * 3600 + m * 60 + x


def hms(t: float) -> str:
    t = int(round(t))
    return f"{t//3600:02d}:{(t%3600)//60:02d}:{t%60:02d}"


# ─────────────────────────── Lecture ───────────────────────────
class Deck:
    def __init__(self, d: dict, lec: "Lecture"):
        self.raw = d
        self.key = d["key"]
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", self.key):
            sys.exit(f"deck key는 ASCII여야 합니다: {self.key!r} (PS/.bat 인코딩 문제)")
        self.name = d["name"]
        self.display = d.get("display", self.name)
        self.period = d.get("period", "")
        self.topic = d.get("topic", self.display)
        self.pdf = d["pdf"]
        self.pptx = d.get("pptx")
        self.lastyear_note_pdf = d.get("lastyear_note_pdf")
        self.lastyear_onepage_pdf = d.get("lastyear_onepage_pdf")
        self.video = (sec(d["video"]["start"]), sec(d["video"]["end"]))
        pad = cfg().get("audio", {}).get("default_pad_s", 10)
        a = d.get("audio")
        if a:
            self.audio = (sec(a["start"]), sec(a["end"]))
        else:
            self.audio = (max(0, self.video[0] - pad), self.video[1] + pad)

    @property
    def stem(self) -> str:
        return Path(self.pdf).stem


class Lecture:
    def __init__(self, root: Path, out_override: Path | None = None):
        self.root = root
        f = root / "lecture.json"
        if not f.exists():
            sys.exit(f"lecture.json 이 없습니다: {f}")
        self.data = json.loads(f.read_text(encoding="utf-8-sig"))
        self.course = self.data.get("course", "")
        self.date = self.data.get("date", "")
        self.professor = self.data.get("professor", "")
        self.mp4 = root / self.data["mp4"]
        self.work = root / self.data.get("work_dir", "_work")
        self.out = out_override or (root / self.data.get("output_dir", "output"))
        self._decks = [Deck(d, self) for d in self.data["decks"]]
        self.index_notes = self.data.get("index_notes", [])
        self.params = self.data.get("params", {})

    # ── 덱 ──
    def keys(self):
        return [d.key for d in self._decks]

    def decks(self):
        return list(self._decks)

    def deck(self, key: str) -> Deck:
        for d in self._decks:
            if d.key == key:
                return d
        sys.exit(f"lecture.json에 없는 deck key: {key!r} (있는 것: {self.keys()})")

    def param(self, name, default=None):
        return self.params.get(name, default)

    # ── 자주 쓰는 값 ──
    def offset(self, key) -> int:
        """오디오 wav의 0초가 영상의 몇 초인지 (= audio.start). 전사 후 변경 금지."""
        return self.deck(key).audio[0]

    def lessons(self):
        return [(d.key, d.video[0], d.video[1]) for d in self._decks]

    def deck_pdf(self, key) -> Path:
        return self.root / self.deck(key).pdf

    def lastyear_pdf(self, key) -> Path | None:
        d = self.deck(key)
        return (self.root / d.lastyear_note_pdf) if d.lastyear_note_pdf else None

    def onepage_pdf(self, key) -> Path | None:
        d = self.deck(key)
        return (self.root / d.lastyear_onepage_pdf) if d.lastyear_onepage_pdf else None

    def title(self, key) -> str:
        return self.deck(key).name

    def display(self, key) -> str:
        return self.deck(key).display

    def period(self, key) -> str:
        return self.deck(key).period

    def stem(self, key) -> str:
        return self.deck(key).stem

    def meta_line(self, key) -> str:
        return f"{self.date} {self.period(key)} · {self.professor} 교수님 · {self.course}"

    def span_text(self, key) -> str:
        a, b = self.deck(key).video
        return f"{hms(a)}~{hms(b)}"

    # ── 경로 ──
    def outdir(self, key) -> Path:
        p = self.out / self.title(key)
        p.mkdir(parents=True, exist_ok=True)
        return p

    def slides_dir(self, key) -> Path:
        return self.out / "_slides" / key

    def audio_dir(self) -> Path:
        return self.work / "audio"

    def audio_wav(self, key) -> Path:
        return self.work / "audio" / f"{key}.wav"

    def raw(self, key, tag="full") -> Path:
        return self.work / "raw" / f"{key}__{tag}.json"

    def bundle(self, key) -> Path:
        return self.work / f"bundle_{key}.json"

    def notes(self, key) -> Path:
        return self.work / f"notes_{key}.json"

    def gaps(self, key) -> Path:
        return self.work / f"gaps_{key}.json"

    def cursor(self, key) -> Path:
        return self.work / f"cursor_{key}.json"

    def recheck(self, key) -> Path:
        return self.work / f"recheck_{key}.json"

    def verify_patch(self, key) -> Path:
        return self.work / f"verify_patch_{key}.json"

    @property
    def slides_json(self) -> Path:
        return self.work / "slides.json"

    @property
    def segments_json(self) -> Path:
        return self.work / "segments.json"

    @property
    def segments_matched(self) -> Path:
        return self.work / "segments_matched.json"

    @property
    def segments_final(self) -> Path:
        return self.work / "segments_final.json"

    @property
    def lastyear_map(self) -> Path:
        return self.work / "lastyear_map.json"

    @property
    def diff_signal(self) -> Path:
        return self.work / "diff_signal.npy"

    @property
    def frames_dir(self) -> Path:
        return self.work / "frames" / "seg"

    def pages_dir(self, key) -> Path:
        return self.work / "pages" / key

    def lastyear_dir(self, key, onepage=False) -> Path:
        return self.work / "lastyear" / (f"{key}_onepage" if onepage else key)

    @property
    def shots_dir(self) -> Path:
        return self.work / "verify_shots"

    @property
    def verify_dir(self) -> Path:
        return self.work / "verify"

    @property
    def logs_dir(self) -> Path:
        return self.work / "logs"

    def load_json(self, path: Path):
        return json.loads(Path(path).read_text(encoding="utf-8"))

    def save_json(self, path: Path, obj, indent=1):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=indent),
                              encoding="utf-8")


# ─────────────────────────── 강의 폴더 찾기 ───────────────────────────
def _pop_opt(argv: list, name: str):
    """argv에서 `--name value` 또는 `--name=value`를 떼어내 값을 돌려준다."""
    val = None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == name and i + 1 < len(argv):
            val = argv[i + 1]
            del argv[i:i + 2]
            continue
        if a.startswith(name + "="):
            val = a.split("=", 1)[1]
            del argv[i]
            continue
        i += 1
    return val


def list_lectures():
    return sorted(p.parent for p in ROOT.glob("*/lecture.json"))


def find_lecture(explicit: str | None = None) -> Path:
    if explicit:
        p = Path(explicit)
        if not p.is_absolute():
            cand = ROOT / explicit
            p = cand if cand.exists() else p.resolve()
        if (p / "lecture.json").exists():
            return p
        sys.exit(f"--lecture 폴더에 lecture.json 이 없습니다: {p}")
    env = os.environ.get("WABEL_LECTURE")
    if env:
        return find_lecture(env)
    cur = Path.cwd().resolve()
    for p in [cur] + list(cur.parents):
        if (p / "lecture.json").exists():
            return p
    cands = list_lectures()
    msg = ["강의 폴더를 찾지 못했습니다. --lecture <폴더> 로 지정하세요."]
    if cands:
        msg.append("후보:")
        msg += [f"  {c.name}" for c in cands]
    sys.exit("\n".join(msg))


def init(argv: list | None = None) -> Lecture:
    """sys.argv에서 --lecture/--out 을 떼어내고 Lecture를 돌려준다."""
    global _LEC
    args = sys.argv if argv is None else argv
    lec_opt = _pop_opt(args, "--lecture")
    out_opt = _pop_opt(args, "--out")
    root = find_lecture(lec_opt)
    out = None
    if out_opt:
        out = Path(out_opt)
        if not out.is_absolute():
            out = root / out
    _LEC = Lecture(root, out)
    return _LEC


def current() -> Lecture:
    return _LEC if _LEC is not None else init()


# ─────────────────────────── whisper 공용 ───────────────────────────
_KEEP = []   # ctranslate2 모델 소멸자 abort 회피


def register_cuda_dlls():
    """venv 안 nvidia/{cudnn,cublas,cuda_nvrtc}/bin 을 DLL 검색 경로에 등록한다.
    (패키지는 설치돼 있는데 PATH에 없어 cudnn_ops64_9.dll 로드 실패로 죽는 것 방지)"""
    nv = Path(sys.prefix) / "Lib" / "site-packages" / "nvidia"
    if not nv.exists():
        return
    for sub in ("cudnn", "cublas", "cuda_nvrtc"):
        b = nv / sub / "bin"
        if b.exists():
            try:
                os.add_dll_directory(str(b))
            except (AttributeError, OSError):
                pass
            os.environ["PATH"] = str(b) + os.pathsep + os.environ.get("PATH", "")


def load_whisper_model():
    """config.json whisper 설정으로 faster-whisper 모델을 연다. 반환: (model, 'cuda/float16')"""
    register_cuda_dlls()
    from faster_whisper import WhisperModel
    w = cfg()["whisper"]
    name = w.get("model", "large-v3")
    try:
        model = WhisperModel(name, device=w.get("device", "cuda"),
                             compute_type=w.get("compute_type", "float16"))
        dev = f"{w.get('device', 'cuda')}/{w.get('compute_type', 'float16')}"
    except Exception as e:                                   # noqa: BLE001
        fb = w.get("fallback", {"device": "cpu", "compute_type": "int8"})
        print(f"⚠ {w.get('device')} 실패({type(e).__name__}) → {fb['device']} 폴백",
              file=sys.stderr)
        model = WhisperModel(name, device=fb["device"], compute_type=fb["compute_type"])
        dev = f"{fb['device']}/{fb['compute_type']}"
    _KEEP.append(model)
    return model, dev, name


_STOP = {
    "there", "these", "those", "which", "their", "about", "other", "cells",
    "cell", "with", "from", "have", "than", "more", "most", "such", "into",
    "after", "before", "between", "often", "usually", "commonly", "should",
    "would", "could", "における",
}


def build_prompt(lec: Lecture, key: str) -> str:
    """덱 슬라이드 텍스트에서 영문 의학 용어를 뽑아 whisper initial_prompt 구성."""
    sl = lec.load_json(lec.slides_json)
    words = {}
    for p in sl[key]["pages"]:
        for w in re.findall(r"[A-Za-z][A-Za-z\-']{4,}", p["text"]):
            lw = w.lower()
            words[lw] = words.get(lw, 0) + 1
    top = [w for w, c in sorted(words.items(), key=lambda x: -x[1]) if w not in _STOP]
    n = int(cfg()["whisper"].get("prompt_terms", 45))
    terms = ", ".join(top[:n])
    tpl = cfg()["whisper"]["prompt_template"]
    return tpl.format(course=lec.course, topic=lec.deck(key).topic, terms=terms)


def prompt_echo_phrases(lec: Lecture) -> list[str]:
    """whisper가 침묵 구간에서 initial_prompt를 되읊은 것을 잡기 위한 문구 목록.
    prompt_template에서 {terms} 앞부분을 course/topic 없이 채워 조각으로 쪼갠다."""
    tpl = cfg()["whisper"]["prompt_template"]
    head = tpl.split("{terms}")[0]
    filled = head.format(course=lec.course, topic="", terms="")
    out = []
    for piece in re.split(r"[.:]", filled):
        piece = re.sub(r"\s+", " ", piece).strip()
        if len(piece) >= 4:
            out.append(piece)
    if lec.course:
        out.append(f"의과대학 {lec.course}".strip())
        out.append(lec.course)
    return out
