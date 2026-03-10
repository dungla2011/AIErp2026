import os
import config
import fitz
import pymupdf4llm
from pathlib import Path
import glob
import tiktoken

os.environ["TOKENIZERS_PARALLELISM"] = "false"

def pdf_to_markdown(pdf_path, output_dir):
    doc = fitz.open(pdf_path)

    md = pymupdf4llm.to_markdown(
        doc,
        header=False,
        footer=False,
        page_separators=True,
        ignore_images=True,
        write_images=False,
        image_path=None
    )

    md_cleaned = md.encode('utf-8', errors='surrogatepass').decode('utf-8', errors='ignore')

    output_path = (Path(output_dir) / Path(pdf_path).stem).with_suffix(".md")

    output_path.write_text(md_cleaned, encoding="utf-8")

    return str(output_path)


def pdfs_to_markdowns(pdf_path, overwrite: bool = False):
    output_dir = Path(config.MARKDOWN_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = Path(pdf_path)

    if not pdf_path.exists():
        print("❌ PDF file not found:", pdf_path)
        return []

    md_path = (output_dir / pdf_path.stem).with_suffix(".md")

    if overwrite or not md_path.exists():
        created_path = pdf_to_markdown(pdf_path, output_dir)
    else:
        created_path = md_path

    if Path(created_path).exists():
        return [str(created_path)]
    else:
        print("❌ Markdown not created:", created_path)
        return []

def estimate_context_tokens(messages: list) -> int:
    try:
        encoding = tiktoken.encoding_for_model("gpt-4")
    except:
        encoding = tiktoken.get_encoding("cl100k_base")
    
    total = 0
    for msg in messages:
        if hasattr(msg, 'content') and msg.content:
            total += len(encoding.encode(str(msg.content)))
    return total
