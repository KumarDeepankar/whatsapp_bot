from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class ProcessingType(str, Enum):
    TEXT_EXTRACT = "text_extract"
    INDEXING = "indexing"
    LLM_EXTRACT = "llm_extract"


class ProcessingStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class FileUploadResponse(BaseModel):
    filename: str
    s3_key: str
    file_type: str
    size: int
    upload_time: datetime
    message: str


class FileInfo(BaseModel):
    filename: str
    s3_key: str
    file_type: str
    size: int
    upload_time: datetime
    processing_status: ProcessingStatus = ProcessingStatus.PENDING
    processing_type: Optional[ProcessingType] = None
    processed_at: Optional[datetime] = None
    extracted_text: Optional[str] = None
    indexed: bool = False


class FileListResponse(BaseModel):
    files: List[FileInfo]
    total_count: int


class ProcessFileRequest(BaseModel):
    s3_key: str
    processing_type: ProcessingType
    custom_prompt: Optional[str] = None


class ProcessFileResponse(BaseModel):
    s3_key: str
    processing_type: ProcessingType
    status: ProcessingStatus
    message: str
    result: Optional[str] = None


class LLMExtractRequest(BaseModel):
    s3_key: str
    prompt: str
    output_format: Optional[str] = "text"  # text, json, markdown


class LLMExtractResponse(BaseModel):
    s3_key: str
    prompt: str
    status: ProcessingStatus
    result: Optional[str] = None
    output_format: str = "text"
    message: str
    extracted_s3_key: Optional[str] = None


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
