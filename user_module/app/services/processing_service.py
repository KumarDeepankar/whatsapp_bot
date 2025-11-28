import base64
import json
import io
from typing import Optional, List
from datetime import datetime
import fitz  # PyMuPDF for PDF processing
from openai import OpenAI

from ..config import get_settings
from ..models.schemas import ProcessingType, ProcessingStatus
from ..database import FileRepository
from .s3_service import get_s3_service


class ProcessingService:
    def __init__(self):
        self.settings = get_settings()
        self.s3_service = get_s3_service()

        # Initialize OpenAI client if API key is available
        if self.settings.OPENAI_API_KEY:
            self.openai_client = OpenAI(api_key=self.settings.OPENAI_API_KEY)
        else:
            self.openai_client = None

    def _convert_pdf_to_images(self, content: bytes) -> List[bytes]:
        """Convert PDF pages to images for LLM processing"""
        images = []
        try:
            doc = fitz.open(stream=content, filetype="pdf")
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                # Render page to image with good resolution
                mat = fitz.Matrix(2.0, 2.0)  # 2x zoom for better quality
                pix = page.get_pixmap(matrix=mat)
                img_bytes = pix.tobytes("png")
                images.append(img_bytes)
            doc.close()
        except Exception as e:
            raise Exception(f"Failed to convert PDF to images: {str(e)}")
        return images

    def _extract_text_from_pdf_basic(self, content: bytes) -> str:
        """Extract text from PDF using PyMuPDF (basic extraction)"""
        text_parts = []
        try:
            doc = fitz.open(stream=content, filetype="pdf")
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                text_parts.append(page.get_text())
            doc.close()
        except Exception as e:
            raise Exception(f"Failed to extract text from PDF: {str(e)}")
        return "\n".join(text_parts)

    def _call_llm_with_text(self, text: str, prompt: str, output_format: str = "text") -> str:
        """Call LLM with text content and custom prompt"""
        if not self.openai_client:
            raise Exception("OpenAI API key not configured")

        format_instructions = ""
        if output_format == "json":
            format_instructions = "\n\nIMPORTANT: Return your response as valid JSON only."
        elif output_format == "markdown":
            format_instructions = "\n\nIMPORTANT: Format your response using Markdown."

        full_prompt = f"{prompt}{format_instructions}\n\nContent:\n{text}"

        try:
            response = self.openai_client.chat.completions.create(
                model=self.settings.LLM_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that extracts and structures information from documents."
                    },
                    {
                        "role": "user",
                        "content": full_prompt
                    }
                ],
                max_tokens=4096
            )
            return response.choices[0].message.content
        except Exception as e:
            raise Exception(f"LLM call failed: {str(e)}")

    def _call_llm_with_image(self, image_content: bytes, prompt: str, output_format: str = "text", image_type: str = "png") -> str:
        """Call LLM with image content and custom prompt"""
        if not self.openai_client:
            raise Exception("OpenAI API key not configured for image processing")

        # Encode image to base64
        base64_image = base64.b64encode(image_content).decode('utf-8')

        format_instructions = ""
        if output_format == "json":
            format_instructions = "\n\nIMPORTANT: Return your response as valid JSON only."
        elif output_format == "markdown":
            format_instructions = "\n\nIMPORTANT: Format your response using Markdown."

        full_prompt = f"{prompt}{format_instructions}"

        mime_type = f"image/{image_type}"
        if image_type in ['jpg', 'jpeg']:
            mime_type = "image/jpeg"

        try:
            response = self.openai_client.chat.completions.create(
                model=self.settings.LLM_MODEL,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": full_prompt
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime_type};base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=4096
            )
            return response.choices[0].message.content
        except Exception as e:
            raise Exception(f"LLM vision call failed: {str(e)}")

    def _call_llm_with_multiple_images(self, images: List[bytes], prompt: str, output_format: str = "text") -> str:
        """Call LLM with multiple images (for multi-page PDFs)"""
        if not self.openai_client:
            raise Exception("OpenAI API key not configured for image processing")

        format_instructions = ""
        if output_format == "json":
            format_instructions = "\n\nIMPORTANT: Return your response as valid JSON only."
        elif output_format == "markdown":
            format_instructions = "\n\nIMPORTANT: Format your response using Markdown."

        full_prompt = f"{prompt}{format_instructions}"

        # Build content with all images
        content = [{"type": "text", "text": full_prompt}]

        for i, img_bytes in enumerate(images):
            base64_image = base64.b64encode(img_bytes).decode('utf-8')
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{base64_image}"
                }
            })

        try:
            response = self.openai_client.chat.completions.create(
                model=self.settings.LLM_MODEL,
                messages=[
                    {
                        "role": "user",
                        "content": content
                    }
                ],
                max_tokens=4096
            )
            return response.choices[0].message.content
        except Exception as e:
            raise Exception(f"LLM vision call failed: {str(e)}")

    def _extract_text_from_image(self, content: bytes, custom_prompt: Optional[str] = None) -> str:
        """Extract text from image using LLM vision capabilities"""
        default_prompt = "Extract all text content from this image. If there is no text, describe what you see in the image. Return only the extracted text or description."
        prompt = custom_prompt or default_prompt
        return self._call_llm_with_image(content, prompt, "text", "jpeg")

    def _extract_text_from_txt(self, content: bytes) -> str:
        """Extract text from text file"""
        try:
            return content.decode('utf-8')
        except UnicodeDecodeError:
            try:
                return content.decode('latin-1')
            except Exception:
                raise Exception("Failed to decode text file")

    def _extract_text_from_json(self, content: bytes) -> str:
        """Extract text from JSON file"""
        try:
            data = json.loads(content.decode('utf-8'))
            return json.dumps(data, indent=2)
        except Exception as e:
            raise Exception(f"Failed to parse JSON file: {str(e)}")

    async def extract_text(self, s3_key: str, custom_prompt: Optional[str] = None) -> str:
        """Extract text from file based on its type"""
        file_info = self.s3_service.get_file_info(s3_key)
        if not file_info:
            raise ValueError(f"File not found: {s3_key}")

        # Update status to processing
        self.s3_service.update_file_status(
            s3_key,
            ProcessingStatus.PROCESSING,
            ProcessingType.TEXT_EXTRACT
        )

        try:
            # Get file content from S3
            content = self.s3_service.get_file_content(s3_key)

            # Extract text based on file type
            file_type = file_info.file_type.lower()

            if file_type in ['jpg', 'jpeg']:
                extracted_text = self._extract_text_from_image(content, custom_prompt)
            elif file_type == 'pdf':
                # For PDFs, use LLM if custom prompt provided or API key available
                if custom_prompt and self.openai_client:
                    # Convert PDF to images and use LLM
                    images = self._convert_pdf_to_images(content)
                    extracted_text = self._call_llm_with_multiple_images(images, custom_prompt)
                elif self.openai_client:
                    # Use LLM with default extraction prompt
                    images = self._convert_pdf_to_images(content)
                    default_prompt = "Extract all text content from these PDF pages. Maintain the structure and formatting as much as possible."
                    extracted_text = self._call_llm_with_multiple_images(images, default_prompt)
                else:
                    # Fallback to basic text extraction
                    extracted_text = self._extract_text_from_pdf_basic(content)
            elif file_type == 'txt':
                extracted_text = self._extract_text_from_txt(content)
                # If custom prompt, process through LLM
                if custom_prompt and self.openai_client:
                    extracted_text = self._call_llm_with_text(extracted_text, custom_prompt)
            elif file_type == 'json':
                extracted_text = self._extract_text_from_json(content)
                # If custom prompt, process through LLM
                if custom_prompt and self.openai_client:
                    extracted_text = self._call_llm_with_text(extracted_text, custom_prompt)
            else:
                raise ValueError(f"Unsupported file type: {file_type}")

            # Update status to completed
            self.s3_service.update_file_status(
                s3_key,
                ProcessingStatus.COMPLETED,
                ProcessingType.TEXT_EXTRACT,
                extracted_text=extracted_text
            )

            return extracted_text

        except Exception as e:
            # Update status to failed
            self.s3_service.update_file_status(
                s3_key,
                ProcessingStatus.FAILED,
                ProcessingType.TEXT_EXTRACT
            )
            raise e

    async def llm_extract(self, s3_key: str, prompt: str, output_format: str = "text") -> str:
        """Extract structured information from file using LLM with custom prompt"""
        # If no OpenAI client, use simulation mode
        if not self.openai_client:
            return await self._simulate_llm_extract(s3_key, prompt, output_format)

        file_info = self.s3_service.get_file_info(s3_key)
        if not file_info:
            raise ValueError(f"File not found: {s3_key}")

        # Try LLM extraction, fall back to simulation on API errors
        try:
            return await self._llm_extract_with_api(s3_key, file_info, prompt, output_format)
        except Exception as e:
            error_msg = str(e).lower()
            # Fall back to simulation on quota/rate limit/auth errors
            if any(err in error_msg for err in ['429', 'quota', 'rate limit', '401', 'unauthorized', 'api key']):
                print(f"LLM API error, falling back to simulation: {e}")
                return await self._simulate_llm_extract(s3_key, prompt, output_format)
            raise e

    async def _llm_extract_with_api(self, s3_key: str, file_info, prompt: str, output_format: str = "text") -> str:
        """Actual LLM extraction using OpenAI API"""

        try:
            # Get file content from S3
            content = self.s3_service.get_file_content(s3_key)
            file_type = file_info.file_type.lower()

            if file_type in ['jpg', 'jpeg']:
                result = self._call_llm_with_image(content, prompt, output_format, "jpeg")
            elif file_type == 'pdf':
                # Convert PDF to images for LLM processing
                images = self._convert_pdf_to_images(content)
                result = self._call_llm_with_multiple_images(images, prompt, output_format)
            elif file_type == 'txt':
                text_content = self._extract_text_from_txt(content)
                result = self._call_llm_with_text(text_content, prompt, output_format)
            elif file_type == 'json':
                text_content = self._extract_text_from_json(content)
                result = self._call_llm_with_text(text_content, prompt, output_format)
            else:
                raise ValueError(f"Unsupported file type: {file_type}")

            return result

        except Exception as e:
            raise e

    async def index_text(self, s3_key: str) -> str:
        """Index text content from file for search"""
        file_info = self.s3_service.get_file_info(s3_key)
        if not file_info:
            raise ValueError(f"File not found: {s3_key}")

        # Update status to processing
        self.s3_service.update_file_status(
            s3_key,
            ProcessingStatus.PROCESSING,
            ProcessingType.INDEXING
        )

        try:
            # Check if text was already extracted
            text_content = file_info.extracted_text

            if not text_content:
                # Extract text first if not available
                content = self.s3_service.get_file_content(s3_key)
                file_type = file_info.file_type.lower()

                if file_type in ['jpg', 'jpeg']:
                    text_content = self._extract_text_from_image(content)
                elif file_type == 'pdf':
                    if self.openai_client:
                        images = self._convert_pdf_to_images(content)
                        text_content = self._call_llm_with_multiple_images(
                            images,
                            "Extract all text content from these PDF pages."
                        )
                    else:
                        text_content = self._extract_text_from_pdf_basic(content)
                elif file_type == 'txt':
                    text_content = self._extract_text_from_txt(content)
                elif file_type == 'json':
                    text_content = self._extract_text_from_json(content)
                else:
                    raise ValueError(f"Unsupported file type: {file_type}")

            # Update status to completed with indexed flag
            self.s3_service.update_file_status(
                s3_key,
                ProcessingStatus.COMPLETED,
                ProcessingType.INDEXING,
                extracted_text=text_content,
                indexed=True
            )

            return f"Successfully indexed file: {file_info.filename}. Word count: {len(text_content.split())}"

        except Exception as e:
            # Update status to failed
            self.s3_service.update_file_status(
                s3_key,
                ProcessingStatus.FAILED,
                ProcessingType.INDEXING
            )
            raise e

    async def _simulate_llm_extract(self, s3_key: str, prompt: str, output_format: str = "text") -> str:
        """Simulate LLM extraction when no API key is configured"""
        import time

        file_info = self.s3_service.get_file_info(s3_key)
        if not file_info:
            raise ValueError(f"File not found: {s3_key}")

        # Get actual file content for basic extraction
        content = self.s3_service.get_file_content(s3_key)
        file_type = file_info.file_type.lower()

        # Extract basic text content
        extracted_text = ""
        if file_type == 'txt':
            extracted_text = self._extract_text_from_txt(content)
        elif file_type == 'json':
            extracted_text = self._extract_text_from_json(content)
        elif file_type == 'pdf':
            extracted_text = self._extract_text_from_pdf_basic(content)
        elif file_type in ['jpg', 'jpeg']:
            extracted_text = "[Image file - text extraction simulated]"

        # Simulate processing delay
        time.sleep(1)

        # Generate simulated response based on output format
        if output_format == "json":
            result = {
                "simulation_mode": True,
                "message": "LLM extraction simulated (no API key configured)",
                "file": file_info.filename,
                "file_type": file_type,
                "prompt_received": prompt,
                "extracted_content": extracted_text[:500] if extracted_text else "No text content available",
                "content_length": len(extracted_text) if extracted_text else 0,
                "note": "Configure OPENAI_API_KEY for actual LLM extraction"
            }
            return json.dumps(result, indent=2)
        elif output_format == "markdown":
            result = f"""# Simulated LLM Extraction

**Mode:** Simulation (No API key configured)

## File Information
- **Filename:** {file_info.filename}
- **Type:** {file_type.upper()}
- **Size:** {file_info.size} bytes

## Prompt Received
> {prompt}

## Extracted Content Preview
```
{extracted_text[:500] if extracted_text else "No text content available"}
```

---
*Note: Configure OPENAI_API_KEY environment variable for actual LLM extraction.*
"""
            return result
        else:
            result = f"""[SIMULATION MODE - No LLM API Key Configured]

File: {file_info.filename}
Type: {file_type.upper()}
Prompt: {prompt}

--- Extracted Content Preview ---
{extracted_text[:500] if extracted_text else "No text content available"}

---
Note: Set OPENAI_API_KEY to enable actual LLM extraction."""
            return result


# Singleton instance
_processing_service: Optional[ProcessingService] = None


def get_processing_service() -> ProcessingService:
    global _processing_service
    if _processing_service is None:
        _processing_service = ProcessingService()
    return _processing_service
