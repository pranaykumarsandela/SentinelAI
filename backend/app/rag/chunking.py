import uuid
from typing import List, Optional
from pydantic import BaseModel
from backend.app.rag.document_loaders import ExtractedDocument


class ChunkItem(BaseModel):
    chunk_id: str
    document_id: str
    chunk_index: int
    content: str
    token_count: int
    page_number: Optional[int] = None
    start_char: int
    end_char: int
    filename: str


class DocumentChunker:
    """
    Recursive Character Text Chunker.
    Splits text across natural boundaries: double newlines, newlines, spaces, characters.
    """

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 80):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = ["\n\n", "\n", ". ", "? ", "! ", " ", ""]

    def _count_tokens(self, text: str) -> int:
        """Approximation of tokens: 1 token ~ 4 characters (min 1)."""
        if not text:
            return 0
        return max(1, len(text) // 4)

    def _split_text(self, text: str) -> List[str]:
        """Recursive splitting based on separators."""
        if len(text) <= self.chunk_size:
            return [text.strip()] if text.strip() else []

        # Find best separator
        chosen_sep = ""
        for sep in self.separators:
            if sep in text:
                chosen_sep = sep
                break

        if not chosen_sep:
            # Fallback hard slice
            chunks = []
            for i in range(0, len(text), self.chunk_size - self.chunk_overlap):
                slice_text = text[i : i + self.chunk_size].strip()
                if slice_text:
                    chunks.append(slice_text)
            return chunks

        parts = text.split(chosen_sep)
        chunks = []
        current_chunk = []
        current_len = 0

        for part in parts:
            part_len = len(part) + (len(chosen_sep) if current_chunk else 0)
            if current_len + part_len <= self.chunk_size:
                current_chunk.append(part)
                current_len += part_len
            else:
                if current_chunk:
                    merged = chosen_sep.join(current_chunk).strip()
                    if merged:
                        chunks.append(merged)
                
                # Check if single part exceeds chunk size
                if len(part) > self.chunk_size:
                    sub_chunks = self._split_text(part)
                    chunks.extend(sub_chunks)
                    current_chunk = []
                    current_len = 0
                else:
                    current_chunk = [part]
                    current_len = len(part)

        if current_chunk:
            merged = chosen_sep.join(current_chunk).strip()
            if merged:
                chunks.append(merged)

        return chunks

    def chunk_document(self, document_id: str, extracted_doc: ExtractedDocument) -> List[ChunkItem]:
        all_chunks: List[ChunkItem] = []
        global_chunk_idx = 0
        global_char_offset = 0

        for page in extracted_doc.pages:
            page_text = page.text
            page_splits = self._split_text(page_text)

            for split in page_splits:
                if not split.strip():
                    continue

                chunk_id = str(uuid.uuid4())
                start_char = global_char_offset
                end_char = start_char + len(split)
                token_count = self._count_tokens(split)

                all_chunks.append(
                    ChunkItem(
                        chunk_id=chunk_id,
                        document_id=document_id,
                        chunk_index=global_chunk_idx,
                        content=split,
                        token_count=token_count,
                        page_number=page.page_number,
                        start_char=start_char,
                        end_char=end_char,
                        filename=extracted_doc.filename
                    )
                )
                global_chunk_idx += 1
                global_char_offset = end_char + 1

        return all_chunks

