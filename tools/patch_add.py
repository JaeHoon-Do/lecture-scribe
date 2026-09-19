# -*- coding: utf-8 -*-
"""검증 결과를 _work/verify_patch_<deck>.json 에 병합한다. stdin으로 JSON 조각을 받는다.
예: echo {"12": {"1": "basal cell nest", "2": "__DROP__"}} | python patch_add.py tumor
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import common  # noqa: E402


def main():
    lec = common.init()
    deck = sys.argv[1]
    p = lec.verify_patch(deck)
    cur = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    add = json.load(sys.stdin)
    for pg, d in add.items():
        cur.setdefault(pg, {}).update(d)
    p.write_text(json.dumps(cur, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{deck}: {len(cur)}쪽 누적")


if __name__ == "__main__":
    main()
