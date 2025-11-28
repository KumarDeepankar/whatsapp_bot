"""
Document Processor Service for WhatsApp KB Onboarding

Handles the complete document onboarding pipeline:
1. File upload & validation
2. Text extraction (PDF, TXT, JSON, Images)
3. Text chunking with smart boundaries
4. Embedding generation (via pluggable providers: Gemini, Ollama)
5. OpenSearch indexing

This replicates the WhatsApp-main onboarding process with a web UI.
"""

import os
import io
import tempfile
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
import json

import fitz  # PyMuPDF

from ..config import get_settings
from .embedding_providers import get_embedding_provider, EmbeddingProvider


class DocumentProcessor:
    """Handles document processing pipeline for KB onboarding"""

    SUPPORTED_EXTENSIONS = ['pdf', 'txt', 'json', 'jpg', 'jpeg', 'png']

    def __init__(self):
        self.settings = get_settings()
        self._embedding_provider: Optional[EmbeddingProvider] = None

        # Initialize embedding provider lazily
        self._init_embedding_provider()

    def _init_embedding_provider(self):
        """Initialize the embedding provider based on configuration"""
        try:
            self._embedding_provider = get_embedding_provider()
        except Exception as e:
            print(f"Warning: Could not initialize embedding provider: {e}")
            self._embedding_provider = None

    @property
    def embedding_provider(self) -> Optional[EmbeddingProvider]:
        """Get the current embedding provider"""
        return self._embedding_provider

    @property
    def embeddings_configured(self) -> bool:
        """Check if embeddings are properly configured"""
        return self._embedding_provider is not None

    def get_embedding_info(self) -> Dict[str, Any]:
        """Get information about the current embedding configuration"""
        if self._embedding_provider is None:
            return {
                "configured": False,
                "error": "No embedding provider configured"
            }

        return {
            "configured": True,
            "provider": self._embedding_provider.name,
            "model": self._embedding_provider.model_name,
            "dimensions": self._embedding_provider.dimensions
        }

    def validate_file(self, filename: str, file_size: int) -> Tuple[bool, str]:
        """Validate file type and size"""
        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''

        if ext not in self.SUPPORTED_EXTENSIONS:
            return False, f"Unsupported file type: .{ext}. Supported: {', '.join(self.SUPPORTED_EXTENSIONS)}"

        max_size = self.settings.MAX_FILE_SIZE_MB * 1024 * 1024
        if file_size > max_size:
            return False, f"File too large. Maximum: {self.settings.MAX_FILE_SIZE_MB}MB"

        return True, "Valid"

    def extract_text_from_pdf(self, file_content: bytes) -> Dict[str, Any]:
        """Extract text from PDF using PyMuPDF (same as WhatsApp-main)"""
        try:
            doc = fitz.open(stream=file_content, filetype="pdf")

            pages_text = []
            total_chars = 0

            for page_num, page in enumerate(doc):
                text = page.get_text("text")
                pages_text.append({
                    "page": page_num + 1,
                    "text": text,
                    "chars": len(text)
                })
                total_chars += len(text)

            full_text = "\n\n".join([p["text"] for p in pages_text])

            doc.close()

            return {
                "success": True,
                "text": full_text,
                "pages": len(pages_text),
                "total_chars": total_chars,
                "pages_detail": pages_text
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"PDF extraction failed: {str(e)}"
            }

    def extract_text_from_txt(self, file_content: bytes) -> Dict[str, Any]:
        """Extract text from TXT file"""
        try:
            # Try different encodings
            for encoding in ['utf-8', 'latin-1', 'cp1252']:
                try:
                    text = file_content.decode(encoding)
                    return {
                        "success": True,
                        "text": text,
                        "pages": 1,
                        "total_chars": len(text)
                    }
                except UnicodeDecodeError:
                    continue

            return {
                "success": False,
                "error": "Could not decode text file"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Text extraction failed: {str(e)}"
            }

    def extract_text_from_json(self, file_content: bytes) -> Dict[str, Any]:
        """Extract text from JSON file"""
        try:
            data = json.loads(file_content.decode('utf-8'))

            # Convert JSON to readable text
            if isinstance(data, list):
                # Handle array of objects (e.g., product catalog)
                text_parts = []
                for i, item in enumerate(data):
                    if isinstance(item, dict):
                        item_text = "\n".join([f"{k}: {v}" for k, v in item.items()])
                        text_parts.append(f"Item {i+1}:\n{item_text}")
                    else:
                        text_parts.append(str(item))
                text = "\n\n".join(text_parts)
            elif isinstance(data, dict):
                text = json.dumps(data, indent=2, ensure_ascii=False)
            else:
                text = str(data)

            return {
                "success": True,
                "text": text,
                "pages": 1,
                "total_chars": len(text),
                "items": len(data) if isinstance(data, list) else 1
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"JSON extraction failed: {str(e)}"
            }

    def extract_text_from_image(self, file_content: bytes, filename: str) -> Dict[str, Any]:
        """Extract text from image using Google Gemini Vision"""
        # Image OCR requires Google API key regardless of embedding provider
        if not self.settings.GOOGLE_API_KEY:
            return {
                "success": False,
                "error": "Google API key not configured for image processing. Set GOOGLE_API_KEY in .env"
            }

        try:
            import base64
            import google.generativeai as genai

            # Configure Gemini for image processing
            genai.configure(api_key=self.settings.GOOGLE_API_KEY)

            # Determine mime type
            ext = filename.rsplit('.', 1)[-1].lower()
            mime_type = f"image/{'jpeg' if ext in ['jpg', 'jpeg'] else ext}"

            # Use Gemini for OCR
            model = genai.GenerativeModel('gemini-1.5-flash')

            image_data = {
                "mime_type": mime_type,
                "data": base64.b64encode(file_content).decode('utf-8')
            }

            response = model.generate_content([
                "Extract all text from this image. If it's a product catalog or document, "
                "extract all product names, descriptions, prices, and details in a structured format. "
                "Return only the extracted text, no explanations.",
                image_data
            ])

            text = response.text.strip()

            return {
                "success": True,
                "text": text,
                "pages": 1,
                "total_chars": len(text),
                "method": "gemini_vision"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Image OCR failed: {str(e)}"
            }

    def extract_text(self, file_content: bytes, filename: str) -> Dict[str, Any]:
        """Extract text from file based on type"""
        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''

        if ext == 'pdf':
            return self.extract_text_from_pdf(file_content)
        elif ext == 'txt':
            return self.extract_text_from_txt(file_content)
        elif ext == 'json':
            return self.extract_text_from_json(file_content)
        elif ext in ['jpg', 'jpeg', 'png']:
            return self.extract_text_from_image(file_content, filename)
        else:
            return {
                "success": False,
                "error": f"Unsupported file type: .{ext}"
            }

    def chunk_text(
        self,
        text: str,
        chunk_size: int = 1000,
        chunk_overlap: int = 200
    ) -> List[Dict[str, Any]]:
        """
        Split text into chunks with overlap (similar to LangChain's RecursiveCharacterTextSplitter)
        Returns list of chunks with metadata
        """
        if not text or len(text.strip()) == 0:
            return []

        # Clean the text
        text = text.strip()

        if len(text) <= chunk_size:
            return [{
                "index": 0,
                "text": text,
                "chars": len(text),
                "start": 0,
                "end": len(text)
            }]

        chunks = []
        start = 0
        chunk_index = 0

        # Separators in order of preference (like RecursiveCharacterTextSplitter)
        separators = ["\n\n", "\n", ". ", "? ", "! ", "; ", ", ", " "]

        while start < len(text):
            end = start + chunk_size

            if end >= len(text):
                # Last chunk
                chunk_text = text[start:].strip()
                if chunk_text:
                    chunks.append({
                        "index": chunk_index,
                        "text": chunk_text,
                        "chars": len(chunk_text),
                        "start": start,
                        "end": len(text)
                    })
                break

            # Try to find a good breaking point
            best_break = end
            for sep in separators:
                # Look for separator in the last portion of the chunk
                search_start = start + (chunk_size // 2)
                sep_pos = text.rfind(sep, search_start, end)
                if sep_pos > search_start:
                    best_break = sep_pos + len(sep)
                    break

            chunk_text = text[start:best_break].strip()
            if chunk_text:
                chunks.append({
                    "index": chunk_index,
                    "text": chunk_text,
                    "chars": len(chunk_text),
                    "start": start,
                    "end": best_break
                })
                chunk_index += 1

            # Move start with overlap
            start = best_break - chunk_overlap
            if start < 0:
                start = best_break

        return chunks

    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text using configured provider"""
        if self._embedding_provider is None:
            raise ValueError(
                "Embedding provider not configured. "
                "Set EMBEDDING_PROVIDER and required API keys in .env"
            )

        return self._embedding_provider.generate_embedding(text)

    def generate_embeddings_batch(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate embeddings for all chunks using configured provider"""
        results = []
        provider_info = self.get_embedding_info()

        for chunk in chunks:
            try:
                embedding = self.generate_embedding(chunk["text"])
                results.append({
                    **chunk,
                    "embedding": embedding,
                    "embedding_status": "success",
                    "embedding_provider": provider_info.get("provider", "unknown"),
                    "embedding_model": provider_info.get("model", "unknown")
                })
            except Exception as e:
                results.append({
                    **chunk,
                    "embedding": None,
                    "embedding_status": "failed",
                    "embedding_error": str(e)
                })

        return results

    def get_processing_stats(self, text: str, chunks: List[Dict]) -> Dict[str, Any]:
        """Get statistics about the processed document"""
        return {
            "total_chars": len(text),
            "total_words": len(text.split()),
            "total_chunks": len(chunks),
            "avg_chunk_size": sum(c["chars"] for c in chunks) // len(chunks) if chunks else 0,
            "min_chunk_size": min(c["chars"] for c in chunks) if chunks else 0,
            "max_chunk_size": max(c["chars"] for c in chunks) if chunks else 0
        }


# Singleton
_processor: Optional[DocumentProcessor] = None

def get_document_processor() -> DocumentProcessor:
    global _processor
    if _processor is None:
        _processor = DocumentProcessor()
    return _processor
