from __future__ import annotations

import ast
from pathlib import Path


SURFACE_MODULES = [
    Path("src/dart_footing_reconciler/audit_workbook.py"),
    Path("src/dart_footing_reconciler/report_html.py"),
    Path("src/dart_footing_reconciler/verify_app.py"),
]


def test_report_surfaces_do_not_duplicate_check_type_registry_dicts() -> None:
    for module_path in SURFACE_MODULES:
        tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))
        duplicated_keys = [
            key.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Dict)
            for key in node.keys
            if isinstance(key, ast.Constant)
            and key.value in {"fs_note_match", "total_check", "cfs_note_match"}
        ]

        assert duplicated_keys == [], f"{module_path} duplicates check-type registry keys"


def test_excel_and_html_surfaces_import_report_frame_registries() -> None:
    workbook_source = Path("src/dart_footing_reconciler/audit_workbook.py").read_text(
        encoding="utf-8"
    )
    html_source = Path("src/dart_footing_reconciler/report_html.py").read_text(encoding="utf-8")
    verify_source = Path("src/dart_footing_reconciler/verify_app.py").read_text(encoding="utf-8")

    assert "CHECK_METHOD_DESCRIPTIONS" in workbook_source
    assert "check_group" in workbook_source
    assert "CHECK_GROUPS" in html_source
    assert "CHECK_METHOD_DESCRIPTIONS" in html_source
    assert "TABLE_UNIT_TOLERANCE_CHECK_TYPES" in html_source
    assert "_build_html" in verify_source
