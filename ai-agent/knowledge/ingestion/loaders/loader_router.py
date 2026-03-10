import os

from .pdf_loader import load_pdf
from .docx_loader import load_docx
from .html_loader import load_html
from .csv_loader import load_csv


def load_document(file_path: str):

    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".pdf":
        return load_pdf(file_path)

    if ext == ".docx":
        return load_docx(file_path)

    if ext in [".html", ".htm"]:
        return load_html(file_path)

    if ext == ".csv":
        return load_csv(file_path)

    raise ValueError(f"Unsupported file type: {ext}")