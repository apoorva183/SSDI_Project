import fitz  # PyMuPDF
from pathlib import Path

def extract_text_from_pdf(file_path: str) -> str:
    """
    Extracts text from a PDF file using PyMuPDF.
    Works for text-based PDFs (not scanned images).
    Returns a clean plain-text string suitable for LLM parsing.
    """
    pdf_path = Path(file_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    text_chunks = []
    with fitz.open(file_path) as doc:
        for page_num, page in enumerate(doc, start=1):
            # Extract text
            text = page.get_text("text")
            if not text.strip():
                print(f"[Warning] Page {page_num} contains little/no extractable text.")
            text_chunks.append(f"\n--- Page {page_num} ---\n{text.strip()}")
    
    raw_text = "\n".join(text_chunks)

    # Light cleanup
    cleaned = (
        raw_text.replace("\r", " ")
        .replace("•", "\n• ")
        .replace("\t", " ")
        .replace("  ", " ")
    )

    # Optional: collapse excessive newlines but keep some structure
    cleaned = "\n".join([line.strip() for line in cleaned.splitlines() if line.strip()])

    return cleaned


# Example usage:
if __name__ == "__main__":
    pdf_file = "NinerMatch_Sample_Resume_Venkata_Sai.pdf"
    resume_text = extract_text_from_pdf(pdf_file)
    print(resume_text[:1000])  # preview first 1k chars
