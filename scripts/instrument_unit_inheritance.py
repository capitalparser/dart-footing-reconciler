"""18-co 코퍼스에서 단위 상속 실태 계측.

표별로 (a) 자체 선언 단위 vs (b) 직전 표에서 상속된 단위인지,
(c) 상속이 본문↔주석 영역 경계를 넘는지 집계한다.
"""
import json
import sys
from pathlib import Path

from dart_footing_reconciler.document import parse_full_report

manifest = json.loads(Path(sys.argv[1]).read_text())
declared = inherited = cross_area = 0
for entry in manifest["companies"]:
    report = parse_full_report(entry["html_path"], company=entry["name"])
    prev_mult, prev_kind = None, None
    for kind, sections in (("statement", report.statements), ("note", report.notes)):
        for section in sections:
            for block in section.blocks:
                if block.table is None:
                    continue
                t = block.table
                own = t.unit_multiplier != (prev_mult or 1) or prev_mult is None
                if own:
                    declared += 1
                else:
                    inherited += 1
                    if prev_kind is not None and prev_kind != kind:
                        cross_area += 1
                prev_mult, prev_kind = t.unit_multiplier, kind
print(f"declared={declared} inherited={inherited} cross_area={cross_area}")
