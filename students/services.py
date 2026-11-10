import os

from pypdf import PdfReader
from docx import Document



def extract_pdf_text(file_path):
    """Extract selectable text from a PDF resume."""
    text_parts = []

    try:
        reader = PdfReader(file_path)

        if reader.is_encrypted:
            return ""

        for page in reader.pages:
            page_text = page.extract_text()

            if page_text and page_text.strip():
                text_parts.append(page_text.strip())

    except Exception:
        return ""

    return "\n".join(text_parts)


def extract_docx_text(file_path):
    """Extract text from paragraphs and tables in a DOCX resume."""
    text_parts = []

    try:
        document = Document(file_path)

        for paragraph in document.paragraphs:
            if paragraph.text.strip():
                text_parts.append(paragraph.text.strip())

        # Resume skills and experience are often stored in tables.
        for table in document.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text.strip():
                        text_parts.append(cell.text.strip())

    except Exception:
        return ""

    return "\n".join(text_parts)



def extract_resume_text(file_path):

    extension = os.path.splitext(
        file_path
    )[1].lower()

    if extension == '.pdf':

        return extract_pdf_text(file_path)

    elif extension == '.docx':

        return extract_docx_text(file_path)

    return ""