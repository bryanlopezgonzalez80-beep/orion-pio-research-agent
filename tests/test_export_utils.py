from __future__ import annotations

import pytest

import export_utils

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("exporter", "signature"),
    [
        (export_utils.export_docx, b"PK"),
        (export_utils.export_pdf, b"%PDF"),
        (export_utils.export_pptx, b"PK"),
    ],
)
def test_exports_are_nonempty_and_valid(exporter, signature, sample_paper):
    payload = exporter([sample_paper], title="Informe Orión ñ")
    assert isinstance(payload, bytes)
    assert len(payload) > 500
    assert payload.startswith(signature)


@pytest.mark.parametrize("exporter", [export_utils.export_docx, export_utils.export_pdf, export_utils.export_pptx])
def test_empty_exports_are_still_valid_documents(exporter):
    assert len(exporter([], title="Vacío ñ")) > 100


def test_plain_text_export_representation_handles_unicode_and_missing_fields(sample_paper):
    text = export_utils._paper_text(sample_paper)
    assert "Liderazgo y seguridad psicológica" in text
    assert "Ana Pérez" in text
    assert "Sin" not in export_utils._paper_text({})
