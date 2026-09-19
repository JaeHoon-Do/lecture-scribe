# -*- coding: utf-8 -*-
"""눈으로 검증한 마커 설명(verify_patch_<deck>.json)을 notes_<deck>.json의 pointers에 반영한다.

__DROP__ 로 시작하는 항목 = 조직이 아니라 여백·화면 밖을 짚은 것.
마커 번호가 밀리면 안 되므로 지우지 않고 '(구조 아님)'으로 남긴다.
원본은 notes_<deck>.json.bak 로 백업.
사용법: python apply_verify.py <deck>
"""
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import common  # noqa: E402


def main(deck):
    lec = common.current()
    npath = lec.notes(deck)
    patch = lec.load_json(lec.verify_patch(deck))
    shutil.copy(npath, npath.with_suffix(".json.bak"))
    data = json.loads(npath.read_text(encoding="utf-8"))
    byp = {p["page"]: p for p in data["pages"]}

    n_new = n_fix = n_drop = 0
    for pg, labs in patch.items():
        pg = int(pg)
        p = byp.get(pg)
        if p is None:
            p = {"page": pg}
            data["pages"].append(p)
            byp[pg] = p
        cur = {int(x["n"]): x for x in p.get("pointers", [])}
        for k, lab in labs.items():
            k = int(k)
            if lab.startswith("__DROP__"):
                lab = lab.replace("__DROP__", "").strip() + " (구조 아님)"
                n_drop += 1
            if k in cur:
                if cur[k].get("label") != lab:
                    n_fix += 1
                cur[k]["label"] = lab
            else:
                cur[k] = {"n": k, "label": lab}
                n_new += 1
        p["pointers"] = [cur[k] for k in sorted(cur)]
    data["pages"].sort(key=lambda x: x["page"])
    npath.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{deck}: 신규 {n_new} · 교정 {n_fix} · 구조아님 표시 {n_drop}")


if __name__ == "__main__":
    common.init()
    main(sys.argv[1])
