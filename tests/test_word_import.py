import zipfile

import pymupdf

from word_import import docx_to_pdf, extract_docx_text


def _write_docx(path):
    xml = """<?xml version='1.0' encoding='UTF-8'?>
    <w:document xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'>
      <w:body>
        <w:p><w:r><w:t>Mario Rossi</w:t></w:r></w:p>
        <w:tbl><w:tr><w:tc><w:p><w:r><w:t>Codice fiscale</w:t></w:r></w:p></w:tc>
        <w:tc><w:p><w:r><w:t>RSSMRA80A01H501U</w:t></w:r></w:p></w:tc></w:tr></w:tbl>
      </w:body>
    </w:document>"""
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", xml)


def test_docx_text_extraction_and_pdf_conversion(tmp_path):
    source = tmp_path / "documento.docx"
    _write_docx(source)
    assert extract_docx_text(source) == ["Mario Rossi", "Codice fiscale | RSSMRA80A01H501U"]
    document = docx_to_pdf(str(source))
    try:
        assert "Mario Rossi" in document[0].get_text()
        assert "RSSMRA80A01H501U" in document[0].get_text()
    finally:
        document.close()


def test_doc_import_is_rejected_explicitly(tmp_path):
    source = tmp_path / "documento.doc"
    source.write_bytes(b"legacy")
    try:
        docx_to_pdf(str(source))
    except ValueError as exc:
        assert "DOCX" in str(exc)
    else:
        raise AssertionError("il formato DOC binario deve essere rifiutato")
