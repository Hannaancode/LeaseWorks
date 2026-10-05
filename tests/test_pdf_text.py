"""Text PDF support uses page citations, independently of the TXT fixtures."""

from io import BytesIO
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject, ArrayObject, TextStringObject
from app.documents import read_document


def test_pdf_text_has_page_location():
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})}
    )
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 50 700 Td (Monthly rent: 8500) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    segments = read_document("lease.pdf", output.getvalue())
    assert segments[0]["text"] == "Monthly rent: 8500"
    assert segments[0]["location"] == "Page 1"


def form_pdf(value, field_type="/Tx", parent_value=False):
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    field = DictionaryObject({
        NameObject("/T"): TextStringObject("Monthly rent"),
        NameObject("/FT"): NameObject(field_type),
    })
    if value is not None:
        field[NameObject("/V")] = TextStringObject(value)
    if parent_value:
        widget = DictionaryObject({NameObject("/Subtype"): NameObject("/Widget"), NameObject("/Parent"): writer._add_object(field)})
    else:
        widget = field
        widget[NameObject("/Subtype")] = NameObject("/Widget")
    page[NameObject("/Annots")] = ArrayObject([writer._add_object(widget)])
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def test_filled_pdf_form_value_is_read_without_page_text():
    segments = read_document("filled.pdf", form_pdf("8500"))
    assert segments == [{"id": "s1", "text": "PDF form field Monthly rent: 8500", "location": "Page 1, form field Monthly rent"}]


def test_form_widget_inherits_parent_value_and_name():
    assert read_document("filled.pdf", form_pdf("9100", parent_value=True))[0]["text"] == "PDF form field Monthly rent: 9100"


def test_blank_and_unchecked_form_values_do_not_create_source_facts():
    import pytest
    for value in (None, "", " ", "/Off"):
        with pytest.raises(ValueError, match="No readable text"):
            read_document("blank.pdf", form_pdf(value))


def test_signature_form_is_not_converted_to_signed_text():
    import pytest
    with pytest.raises(ValueError, match="No readable text"):
        read_document("signed.pdf", form_pdf("Unverified", field_type="/Sig"))
