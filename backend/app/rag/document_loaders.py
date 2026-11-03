import io
import os
from typing import List, Optional
from pydantic import BaseModel
import pypdf
import docx


class DocumentPage(BaseModel):
    page_number: Optional[int] = None
    text: str


class ExtractedDocument(BaseModel):
    filename: str
    file_type: str
    file_size_bytes: int
    content_hash: str
    pages: List[DocumentPage]
    total_characters: int


class DocumentLoaderError(Exception):
    """Custom exception for document loading and parsing errors."""
    pass


class DocumentLoader:
    """Document Ingestion and Text Extraction Engine."""

    SUPPORTED_EXTENSIONS = {
        ".pdf": "PDF",
        ".txt": "TXT",
        ".md": "MARKDOWN",
        ".markdown": "MARKDOWN",
        ".docx": "DOCX",
    }
    
    MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB

    @classmethod
    def validate_file(cls, filename: str, content_bytes: bytes) -> str:
        """Validates filename extension and payload size. Returns normalized file_type."""
        if not filename or "." not in filename:
            raise DocumentLoaderError("Invalid filename: missing extension")
            
        ext = os.path.splitext(filename)[1].lower()
        if ext not in cls.SUPPORTED_EXTENSIONS:
            raise DocumentLoaderError(
                f"Unsupported file format '{ext}'. Supported formats: {list(cls.SUPPORTED_EXTENSIONS.keys())}"
            )
            
        if len(content_bytes) == 0:
            raise DocumentLoaderError("Uploaded file is empty (0 bytes)")
            
        if len(content_bytes) > cls.MAX_FILE_SIZE_BYTES:
            raise DocumentLoaderError(
                f"File size exceeds maximum threshold ({len(content_bytes)} > {cls.MAX_FILE_SIZE_BYTES} bytes)"
            )
            
        return cls.SUPPORTED_EXTENSIONS[ext]

    @classmethod
    def load_bytes(cls, filename: str, content_bytes: bytes, content_hash: str) -> ExtractedDocument:
        file_type = cls.validate_file(filename, content_bytes)
        pages: List[DocumentPage] = []

        try:
            if file_type == "PDF":
                pages = cls._extract_pdf(content_bytes)
            elif file_type == "DOCX":
                pages = cls._extract_docx(content_bytes)
            elif file_type in ("TXT", "MARKDOWN"):
                pages = cls._extract_text(content_bytes)
            else:
                raise DocumentLoaderError(f"Unhandled file type: {file_type}")
        except Exception as e:
            if isinstance(e, DocumentLoaderError):
                raise
            raise DocumentLoaderError(f"Failed to extract text from {filename}: {str(e)}") from e

        total_chars = sum(len(p.text) for p in pages)
        if total_chars == 0:
            raise DocumentLoaderError(f"File '{filename}' contains no extractable text content")

        return ExtractedDocument(
            filename=filename,
            file_type=file_type,
            file_size_bytes=len(content_bytes),
            content_hash=content_hash,
            pages=pages,
            total_characters=total_chars
        )

    @classmethod
    def _extract_pdf(cls, content_bytes: bytes) -> List[DocumentPage]:
        stream = io.BytesIO(content_bytes)
        reader = pypdf.PdfReader(stream)
        pages = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            if text.strip():
                pages.append(DocumentPage(page_number=i + 1, text=text.strip()))
        return pages

    @classmethod
    def _extract_docx(cls, content_bytes: bytes) -> List[DocumentPage]:
        stream = io.BytesIO(content_bytes)
        doc = docx.Document(stream)
        text_lines = []
        for para in doc.paragraphs:
            if para.text.strip():
                text_lines.append(para.text.strip())
        for table in doc.tables:
            for row in table.rows:
                row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                if row_text:
                    text_lines.append(row_text)
                    
        full_text = "\n\n".join(text_lines)
        if full_text.strip():
            return [DocumentPage(page_number=1, text=full_text)]
        return []

    @classmethod
    def _extract_text(cls, content_bytes: bytes) -> List[DocumentPage]:
        # Try UTF-8 first, fallback to latin-1
        try:
            text = content_bytes.decode("utf-8")
        except UnicodeDecodeError:
            text = content_bytes.decode("latin-1")
            
        return [DocumentPage(page_number=1, text=text.strip())]

