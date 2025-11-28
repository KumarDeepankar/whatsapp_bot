from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from typing import Optional

from ..models.schemas import (
    FileUploadResponse,
    FileListResponse,
    FileInfo,
    ProcessFileRequest,
    ProcessFileResponse,
    LLMExtractRequest,
    LLMExtractResponse,
    ProcessingType,
    ProcessingStatus,
    ErrorResponse
)
from ..services.s3_service import get_s3_service
from ..services.processing_service import get_processing_service

router = APIRouter(prefix="/api/files", tags=["files"])


@router.post("/upload", response_model=FileUploadResponse)
async def upload_file(file: UploadFile = File(...)):
    """Upload a file to S3"""
    try:
        s3_service = get_s3_service()
        file_info = await s3_service.upload_file(file)

        return FileUploadResponse(
            filename=file_info.filename,
            s3_key=file_info.s3_key,
            file_type=file_info.file_type,
            size=file_info.size,
            upload_time=file_info.upload_time,
            message=f"File '{file_info.filename}' uploaded successfully"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.get("/list", response_model=FileListResponse)
async def list_files():
    """List all uploaded files with their processing status"""
    try:
        s3_service = get_s3_service()
        files = s3_service.list_files()

        return FileListResponse(
            files=files,
            total_count=len(files)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list files: {str(e)}")


@router.post("/process", response_model=ProcessFileResponse)
async def process_file(request: ProcessFileRequest):
    """Process a file - either extract text or index it"""
    try:
        processing_service = get_processing_service()
        s3_service = get_s3_service()

        # Verify file exists
        file_info = s3_service.get_file_info(request.s3_key)
        if not file_info:
            raise HTTPException(status_code=404, detail=f"File not found: {request.s3_key}")

        result = ""
        if request.processing_type == ProcessingType.TEXT_EXTRACT:
            result = await processing_service.extract_text(request.s3_key, request.custom_prompt)
        elif request.processing_type == ProcessingType.INDEXING:
            result = await processing_service.index_text(request.s3_key)
        else:
            raise HTTPException(status_code=400, detail="Invalid processing type")

        return ProcessFileResponse(
            s3_key=request.s3_key,
            processing_type=request.processing_type,
            status=ProcessingStatus.COMPLETED,
            message=f"File processed successfully using {request.processing_type.value}",
            result=result
        )
    except HTTPException:
        raise
    except Exception as e:
        return ProcessFileResponse(
            s3_key=request.s3_key,
            processing_type=request.processing_type,
            status=ProcessingStatus.FAILED,
            message=f"Processing failed: {str(e)}",
            result=None
        )


@router.post("/llm-extract", response_model=LLMExtractResponse)
async def llm_extract(request: LLMExtractRequest):
    """Extract structured information from a file using LLM with custom prompt"""
    try:
        processing_service = get_processing_service()
        s3_service = get_s3_service()

        # Verify file exists
        file_info = s3_service.get_file_info(request.s3_key)
        if not file_info:
            raise HTTPException(status_code=404, detail=f"File not found: {request.s3_key}")

        output_format = request.output_format or "text"

        result = await processing_service.llm_extract(
            s3_key=request.s3_key,
            prompt=request.prompt,
            output_format=output_format
        )

        # Save extracted text to S3 and update status
        extracted_s3_key = s3_service.save_extracted_text(
            original_s3_key=request.s3_key,
            extracted_text=result,
            output_format=output_format
        )

        # Update file status to completed with extracted text
        s3_service.update_file_status(
            s3_key=request.s3_key,
            status=ProcessingStatus.COMPLETED,
            processing_type=ProcessingType.LLM_EXTRACT,
            extracted_text=result
        )

        return LLMExtractResponse(
            s3_key=request.s3_key,
            prompt=request.prompt,
            status=ProcessingStatus.COMPLETED,
            result=result,
            output_format=output_format,
            message="LLM extraction completed successfully",
            extracted_s3_key=extracted_s3_key
        )
    except HTTPException:
        raise
    except Exception as e:
        # Update status to failed
        try:
            s3_service = get_s3_service()
            s3_service.update_file_status(
                s3_key=request.s3_key,
                status=ProcessingStatus.FAILED,
                processing_type=ProcessingType.LLM_EXTRACT
            )
        except:
            pass

        return LLMExtractResponse(
            s3_key=request.s3_key,
            prompt=request.prompt,
            status=ProcessingStatus.FAILED,
            result=None,
            output_format=request.output_format or "text",
            message=f"LLM extraction failed: {str(e)}"
        )


@router.get("/info/{s3_key:path}", response_model=FileInfo)
async def get_file_info(s3_key: str):
    """Get detailed information about a specific file"""
    try:
        s3_service = get_s3_service()
        file_info = s3_service.get_file_info(s3_key)

        if not file_info:
            raise HTTPException(status_code=404, detail=f"File not found: {s3_key}")

        return file_info
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get file info: {str(e)}")


@router.delete("/{s3_key:path}")
async def delete_file(s3_key: str):
    """Delete a file from S3"""
    try:
        s3_service = get_s3_service()

        # Verify file exists
        file_info = s3_service.get_file_info(s3_key)
        if not file_info:
            raise HTTPException(status_code=404, detail=f"File not found: {s3_key}")

        s3_service.delete_file(s3_key)

        return {"message": f"File '{file_info.filename}' deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete file: {str(e)}")


@router.post("/sync")
async def sync_from_s3():
    """Sync database with files from S3 (recover database from S3 ground truth)"""
    try:
        s3_service = get_s3_service()
        result = s3_service.sync_from_s3()

        return {
            "status": "success",
            "message": f"Synced {result['synced']} files from S3",
            "synced": result['synced'],
            "skipped": result['skipped'],
            "total_in_s3": result['total_in_s3'],
            "errors": result['errors'] if result['errors'] else None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")
