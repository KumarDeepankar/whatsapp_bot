"""
Knowledge Base Router for WhatsApp Bot Integration

Provides step-wise document onboarding:
1. Upload & Validate (+ S3 backup)
2. Extract Text (+ S3 backup)
3. Chunk & Preview
4. Generate Embeddings
5. Index to OpenSearch (+ DB record for Files tab sync)

Also provides:
- Index management
- Search functionality
- Document management
- Re-indexing from Files tab
"""

from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
import base64
import json
import hashlib

from ..services.opensearch_service import get_opensearch_service
from ..services.document_processor import get_document_processor
from ..services.s3_service import get_s3_service
from ..database import FileRepository
from ..models.schemas import FileInfo, ProcessingStatus, ProcessingType

router = APIRouter(prefix="/api/knowledge-base", tags=["knowledge-base"])


# ==========================================
# Request/Response Models
# ==========================================

class ChunkingConfig(BaseModel):
    chunk_size: int = 1000
    chunk_overlap: int = 200


class IndexRequest(BaseModel):
    filename: str
    text: str
    chunks: List[Dict[str, Any]]
    metadata: Optional[Dict[str, Any]] = None


# ==========================================
# Step 1: Upload & Validate (+ S3 Backup)
# ==========================================

@router.post("/onboard/step1-upload")
async def step1_upload_validate(file: UploadFile = File(...)):
    """
    Step 1: Upload file, validate, and store in S3 for backup
    Returns: file info, validation status, and S3 key
    """
    processor = get_document_processor()
    s3_service = get_s3_service()

    # Read file content
    content = await file.read()
    file_size = len(content)

    # Validate
    is_valid, message = processor.validate_file(file.filename, file_size)

    if not is_valid:
        raise HTTPException(status_code=400, detail=message)

    # Get file extension
    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''

    # Generate S3 key with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    doc_hash = hashlib.md5(f"{file.filename}{timestamp}".encode()).hexdigest()[:8]
    s3_key = f"{s3_service.folder_prefix}kb_{timestamp}_{doc_hash}_{file.filename}"

    # Upload original file to S3 for backup
    try:
        content_types = {
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'png': 'image/png',
            'pdf': 'application/pdf',
            'txt': 'text/plain',
            'json': 'application/json'
        }
        content_type = content_types.get(ext, 'application/octet-stream')

        s3_service.s3_client.put_object(
            Bucket=s3_service.bucket_name,
            Key=s3_key,
            Body=content,
            ContentType=content_type
        )
        s3_uploaded = True
    except Exception as e:
        # Log error but don't fail - S3 is for backup
        print(f"Warning: S3 upload failed: {e}")
        s3_uploaded = False

    # Encode content for passing to next step
    content_b64 = base64.b64encode(content).decode('utf-8')

    return {
        "success": True,
        "step": 1,
        "filename": file.filename,
        "file_type": ext,
        "file_size": file_size,
        "file_size_formatted": f"{file_size / 1024:.1f} KB" if file_size < 1024*1024 else f"{file_size / (1024*1024):.2f} MB",
        "content_b64": content_b64,
        "s3_key": s3_key,
        "s3_uploaded": s3_uploaded,
        "message": f"File '{file.filename}' uploaded and validated successfully" + (" (S3 backup created)" if s3_uploaded else " (S3 backup failed)")
    }


# ==========================================
# Step 2: Extract Text (+ S3 Backup)
# ==========================================

@router.post("/onboard/step2-extract")
async def step2_extract_text(
    filename: str = Form(...),
    content_b64: str = Form(...),
    s3_key: str = Form(...)
):
    """
    Step 2: Extract text from the uploaded file and save to S3
    Returns: extracted text with stats
    """
    processor = get_document_processor()
    s3_service = get_s3_service()

    # Decode content
    try:
        content = base64.b64decode(content_b64)
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid file content")

    # Extract text
    result = processor.extract_text(content, filename)

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "Extraction failed"))

    extracted_text = result["text"]

    # Save extracted text to S3 for backup
    extracted_s3_key = None
    try:
        extracted_s3_key = s3_service.save_extracted_text(s3_key, extracted_text, "text")
        extracted_saved = True
    except Exception as e:
        print(f"Warning: Failed to save extracted text to S3: {e}")
        extracted_saved = False

    return {
        "success": True,
        "step": 2,
        "filename": filename,
        "text": extracted_text,
        "pages": result.get("pages", 1),
        "total_chars": result.get("total_chars", len(extracted_text)),
        "total_words": len(extracted_text.split()),
        "preview": extracted_text[:500] + "..." if len(extracted_text) > 500 else extracted_text,
        "s3_key": s3_key,
        "extracted_s3_key": extracted_s3_key,
        "extracted_saved": extracted_saved,
        "message": f"Extracted {result.get('total_chars', 0):,} characters from {result.get('pages', 1)} page(s)" + (" (saved to S3)" if extracted_saved else "")
    }


# ==========================================
# Step 3: Chunk Text
# ==========================================

@router.post("/onboard/step3-chunk")
async def step3_chunk_text(
    filename: str = Form(...),
    text: str = Form(...),
    chunk_size: int = Form(default=1000),
    chunk_overlap: int = Form(default=200)
):
    """
    Step 3: Split text into chunks
    Returns: chunks with preview
    """
    processor = get_document_processor()

    # Validate parameters
    if chunk_size < 100 or chunk_size > 5000:
        raise HTTPException(status_code=400, detail="Chunk size must be between 100 and 5000")
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise HTTPException(status_code=400, detail="Overlap must be >= 0 and < chunk size")

    # Chunk the text
    chunks = processor.chunk_text(text, chunk_size, chunk_overlap)

    if not chunks:
        raise HTTPException(status_code=400, detail="No chunks generated. Text may be empty.")

    # Get stats
    stats = processor.get_processing_stats(text, chunks)

    # Create preview (first 3 chunks)
    chunks_preview = [
        {
            "index": c["index"],
            "preview": c["text"][:200] + "..." if len(c["text"]) > 200 else c["text"],
            "chars": c["chars"]
        }
        for c in chunks[:3]
    ]

    return {
        "success": True,
        "step": 3,
        "filename": filename,
        "chunks": chunks,
        "chunks_preview": chunks_preview,
        "stats": stats,
        "config": {
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap
        },
        "message": f"Created {len(chunks)} chunks (avg {stats['avg_chunk_size']} chars each)"
    }


# ==========================================
# Step 4: Generate Embeddings
# ==========================================

@router.post("/onboard/step4-embed")
async def step4_generate_embeddings(
    filename: str = Form(...),
    chunks_json: str = Form(...)
):
    """
    Step 4: Generate embeddings for all chunks
    Returns: chunks with embeddings and status
    """
    import json

    processor = get_document_processor()

    # Parse chunks
    try:
        chunks = json.loads(chunks_json)
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid chunks data")

    if not chunks:
        raise HTTPException(status_code=400, detail="No chunks to process")

    # Generate embeddings
    embedded_chunks = processor.generate_embeddings_batch(chunks)

    # Count successes and failures
    success_count = sum(1 for c in embedded_chunks if c.get("embedding_status") == "success")
    failed_count = len(embedded_chunks) - success_count

    return {
        "success": success_count > 0,
        "step": 4,
        "filename": filename,
        "chunks": embedded_chunks,
        "total_chunks": len(embedded_chunks),
        "successful": success_count,
        "failed": failed_count,
        "embedding_dimension": len(embedded_chunks[0]["embedding"]) if embedded_chunks and embedded_chunks[0].get("embedding") else 0,
        "message": f"Generated embeddings for {success_count}/{len(embedded_chunks)} chunks"
    }


# ==========================================
# Step 5: Index to OpenSearch (+ DB Record)
# ==========================================

@router.post("/onboard/step5-index")
async def step5_index_to_opensearch(
    filename: str = Form(...),
    file_type: str = Form(...),
    file_size: int = Form(...),
    s3_key: str = Form(...),
    extracted_text: str = Form(...),
    chunks_json: str = Form(...),
    metadata_json: str = Form(default="{}")
):
    """
    Step 5: Index all chunks to OpenSearch and create DB record for Files tab sync
    Returns: indexing results
    """
    opensearch = get_opensearch_service()

    # Parse data
    try:
        chunks = json.loads(chunks_json)
        metadata = json.loads(metadata_json)
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid data format")

    if not chunks:
        raise HTTPException(status_code=400, detail="No chunks to index")

    # Ensure index exists
    opensearch.create_index(recreate=False)

    # Index each chunk
    indexed_count = 0
    errors = []
    doc_ids = []

    try:
        with opensearch._get_client() as client:
            for chunk in chunks:
                if not chunk.get("embedding"):
                    errors.append(f"Chunk {chunk.get('index', '?')}: No embedding")
                    continue

                try:
                    doc = {
                        "content": chunk["text"],
                        "content_embedding": chunk["embedding"],
                        "filename": filename,
                        "s3_key": s3_key,
                        "file_type": file_type,
                        "chunk_index": chunk["index"],
                        "total_chunks": len(chunks),
                        "indexed_at": datetime.utcnow().isoformat(),
                        "metadata": {
                            **metadata,
                            "chars": chunk.get("chars", 0),
                            "onboarding_method": "kb_stepwise",
                            "embedding_provider": chunk.get("embedding_provider", "unknown"),
                            "embedding_model": chunk.get("embedding_model", "unknown")
                        }
                    }

                    response = client.post(
                        f"/{opensearch.index_name}/_doc?refresh=true",
                        json=doc
                    )
                    response.raise_for_status()
                    result = response.json()

                    doc_ids.append(result["_id"])
                    indexed_count += 1

                except Exception as e:
                    errors.append(f"Chunk {chunk.get('index', '?')}: {str(e)}")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OpenSearch connection failed: {str(e)}")

    # Create database record for Files tab sync (only if indexing succeeded)
    db_created = False
    if indexed_count > 0:
        try:
            # Check if record already exists
            existing = FileRepository.get_by_s3_key(s3_key)
            if not existing:
                file_info = FileInfo(
                    filename=filename,
                    s3_key=s3_key,
                    file_type=file_type,
                    size=file_size,
                    upload_time=datetime.now(),
                    processing_status=ProcessingStatus.COMPLETED,
                    processing_type=ProcessingType.INDEXING,
                    processed_at=datetime.now(),
                    extracted_text=extracted_text,
                    indexed=True
                )
                FileRepository.create(file_info)
                db_created = True
            else:
                # Update existing record
                FileRepository.update_status(
                    s3_key=s3_key,
                    status=ProcessingStatus.COMPLETED,
                    processing_type=ProcessingType.INDEXING,
                    extracted_text=extracted_text,
                    indexed=True
                )
                db_created = True
        except Exception as e:
            print(f"Warning: Failed to create/update DB record: {e}")

    return {
        "success": indexed_count > 0,
        "step": 5,
        "filename": filename,
        "s3_key": s3_key,
        "indexed_chunks": indexed_count,
        "total_chunks": len(chunks),
        "failed_chunks": len(errors),
        "doc_ids": doc_ids,
        "errors": errors if errors else None,
        "db_synced": db_created,
        "message": f"Successfully indexed {indexed_count}/{len(chunks)} chunks to knowledge base" + (" (synced to Files tab)" if db_created else "")
    }


# ==========================================
# One-Click Full Onboarding (with S3 + DB)
# ==========================================

@router.post("/onboard/full")
async def full_onboarding(
    file: UploadFile = File(...),
    chunk_size: int = Form(default=1000),
    chunk_overlap: int = Form(default=200)
):
    """
    Complete onboarding in one request (for automation)
    Combines all 5 steps with S3 backup and DB sync
    """
    processor = get_document_processor()
    opensearch = get_opensearch_service()
    s3_service = get_s3_service()

    results = {
        "filename": file.filename,
        "steps": {}
    }

    try:
        # Step 1: Upload & Validate
        content = await file.read()
        file_size = len(content)
        is_valid, message = processor.validate_file(file.filename, file_size)

        if not is_valid:
            raise HTTPException(status_code=400, detail=message)

        ext = file.filename.rsplit('.', 1)[-1].lower()

        # Generate S3 key and upload to S3
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        doc_hash = hashlib.md5(f"{file.filename}{timestamp}".encode()).hexdigest()[:8]
        s3_key = f"{s3_service.folder_prefix}kb_{timestamp}_{doc_hash}_{file.filename}"

        s3_uploaded = False
        try:
            content_types = {
                'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png',
                'pdf': 'application/pdf', 'txt': 'text/plain', 'json': 'application/json'
            }
            s3_service.s3_client.put_object(
                Bucket=s3_service.bucket_name,
                Key=s3_key,
                Body=content,
                ContentType=content_types.get(ext, 'application/octet-stream')
            )
            s3_uploaded = True
        except Exception as e:
            print(f"Warning: S3 upload failed: {e}")

        results["steps"]["upload"] = {"success": True, "file_size": file_size, "s3_uploaded": s3_uploaded}

        # Step 2: Extract Text
        extraction = processor.extract_text(content, file.filename)
        if not extraction["success"]:
            raise HTTPException(status_code=400, detail=extraction.get("error"))

        extracted_text = extraction["text"]

        # Save extracted text to S3
        extracted_saved = False
        try:
            s3_service.save_extracted_text(s3_key, extracted_text, "text")
            extracted_saved = True
        except Exception as e:
            print(f"Warning: Failed to save extracted text: {e}")

        results["steps"]["extract"] = {
            "success": True,
            "pages": extraction.get("pages", 1),
            "chars": extraction.get("total_chars", 0),
            "extracted_saved": extracted_saved
        }

        # Step 3: Chunk Text
        chunks = processor.chunk_text(extracted_text, chunk_size, chunk_overlap)
        results["steps"]["chunk"] = {"success": True, "total_chunks": len(chunks)}

        # Step 4: Generate Embeddings
        embedded_chunks = processor.generate_embeddings_batch(chunks)
        success_embeddings = sum(1 for c in embedded_chunks if c.get("embedding"))
        results["steps"]["embed"] = {
            "success": success_embeddings > 0,
            "successful": success_embeddings,
            "failed": len(embedded_chunks) - success_embeddings
        }

        # Step 5: Index to OpenSearch
        opensearch.create_index(recreate=False)

        indexed_count = 0
        with opensearch._get_client() as client:
            for chunk in embedded_chunks:
                if not chunk.get("embedding"):
                    continue

                doc = {
                    "content": chunk["text"],
                    "content_embedding": chunk["embedding"],
                    "filename": file.filename,
                    "s3_key": s3_key,
                    "file_type": ext,
                    "chunk_index": chunk["index"],
                    "total_chunks": len(chunks),
                    "indexed_at": datetime.utcnow().isoformat(),
                    "metadata": {
                        "onboarding_method": "full_auto",
                        "embedding_provider": chunk.get("embedding_provider", "unknown"),
                        "embedding_model": chunk.get("embedding_model", "unknown")
                    }
                }

                response = client.post(f"/{opensearch.index_name}/_doc?refresh=true", json=doc)
                if response.status_code in [200, 201]:
                    indexed_count += 1

        # Create DB record for Files tab sync
        db_synced = False
        if indexed_count > 0:
            try:
                existing = FileRepository.get_by_s3_key(s3_key)
                if not existing:
                    file_info = FileInfo(
                        filename=file.filename,
                        s3_key=s3_key,
                        file_type=ext,
                        size=file_size,
                        upload_time=datetime.now(),
                        processing_status=ProcessingStatus.COMPLETED,
                        processing_type=ProcessingType.INDEXING,
                        processed_at=datetime.now(),
                        extracted_text=extracted_text,
                        indexed=True
                    )
                    FileRepository.create(file_info)
                    db_synced = True
            except Exception as e:
                print(f"Warning: Failed to create DB record: {e}")

        results["steps"]["index"] = {"success": indexed_count > 0, "indexed": indexed_count, "db_synced": db_synced}
        results["success"] = indexed_count > 0
        results["s3_key"] = s3_key
        results["s3_uploaded"] = s3_uploaded
        results["db_synced"] = db_synced
        results["message"] = f"Successfully onboarded '{file.filename}' with {indexed_count} chunks"

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return results


# ==========================================
# Index Management Endpoints
# ==========================================

@router.get("/status")
async def get_status() -> Dict[str, Any]:
    """Get OpenSearch connection status, index stats, and embedding provider info"""
    opensearch = get_opensearch_service()
    processor = get_document_processor()

    # OpenSearch status
    conn_status = opensearch.test_connection()

    if not conn_status["connected"]:
        opensearch_info = {
            "connected": False,
            "error": conn_status.get("error", "Unknown connection error")
        }
    else:
        stats = opensearch.get_index_stats()
        opensearch_info = {
            "connected": True,
            "cluster_name": conn_status.get("cluster_name"),
            "version": conn_status.get("version"),
            "index": {
                "name": opensearch.index_name,
                "exists": stats.get("exists", False),
                "total_chunks": stats.get("total_chunks", 0),
                "unique_documents": stats.get("unique_documents", 0),
                "size_mb": stats.get("size_mb", 0)
            }
        }

    # Embedding provider info
    embedding_info = processor.get_embedding_info()

    return {
        **opensearch_info,
        "embedding": embedding_info
    }


@router.get("/embedding/status")
async def get_embedding_status() -> Dict[str, Any]:
    """Get detailed embedding provider status and health check"""
    from ..services.embedding_providers import EmbeddingProviderFactory

    # Check all providers
    all_providers = EmbeddingProviderFactory.check_all_providers()

    # Get current provider info
    processor = get_document_processor()
    current_provider = processor.get_embedding_info()

    return {
        "current_provider": current_provider,
        "available_providers": all_providers
    }


@router.post("/index/create")
async def create_index(recreate: bool = False) -> Dict[str, Any]:
    """Create or recreate the knowledge base index"""
    opensearch = get_opensearch_service()
    result = opensearch.create_index(recreate=recreate)

    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["message"])

    return result


@router.delete("/index")
async def delete_index() -> Dict[str, Any]:
    """Delete the entire knowledge base index"""
    opensearch = get_opensearch_service()
    result = opensearch.delete_index()

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Failed to delete index"))

    return result


# ==========================================
# Document Management Endpoints
# ==========================================

@router.get("/documents")
async def list_indexed_documents() -> Dict[str, Any]:
    """List all documents in the knowledge base"""
    opensearch = get_opensearch_service()
    documents = opensearch.list_indexed_documents()

    return {
        "documents": documents,
        "total": len(documents)
    }


@router.delete("/documents/{s3_key:path}")
async def remove_document(s3_key: str) -> Dict[str, Any]:
    """Remove a document from the knowledge base"""
    opensearch = get_opensearch_service()
    result = opensearch.delete_document(s3_key)

    if not result["success"]:
        raise HTTPException(status_code=500, detail=result.get("error", "Delete failed"))

    return {
        "success": True,
        "message": f"Removed document from knowledge base",
        "deleted_chunks": result["deleted"]
    }


# ==========================================
# Search Endpoints
# ==========================================

@router.get("/search")
async def search_knowledge_base(
    query: str = Query(..., min_length=1),
    k: int = Query(default=5, ge=1, le=20),
    use_hybrid: bool = Query(default=True)
) -> Dict[str, Any]:
    """Search the knowledge base"""
    opensearch = get_opensearch_service()

    try:
        results = opensearch.search(query=query, k=k, use_hybrid=use_hybrid)

        return {
            "query": query,
            "results": results,
            "total_results": len(results)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.post("/search")
async def search_knowledge_base_post(
    query: str = Form(...),
    k: int = Form(default=5)
) -> Dict[str, Any]:
    """Search the knowledge base (POST)"""
    return await search_knowledge_base(query=query, k=k)


# ==========================================
# Re-Index from Files Tab
# ==========================================

@router.post("/reindex/{s3_key:path}")
async def reindex_document(
    s3_key: str,
    chunk_size: int = Query(default=1000),
    chunk_overlap: int = Query(default=200)
) -> Dict[str, Any]:
    """
    Re-index a document from the Files tab.
    Fetches file from S3, re-extracts, re-chunks, re-embeds, and re-indexes.
    Useful when embedding model changes or to update chunking config.
    """
    processor = get_document_processor()
    opensearch = get_opensearch_service()
    s3_service = get_s3_service()

    # Get file info from database
    file_info = FileRepository.get_by_s3_key(s3_key)
    if not file_info:
        raise HTTPException(status_code=404, detail=f"File not found in database: {s3_key}")

    results = {
        "s3_key": s3_key,
        "filename": file_info.filename,
        "steps": {}
    }

    try:
        # Step 1: Download from S3
        try:
            content = s3_service.get_file_content(s3_key)
            results["steps"]["download"] = {"success": True, "size": len(content)}
        except Exception as e:
            raise HTTPException(status_code=404, detail=f"Failed to download from S3: {str(e)}")

        # Step 2: Extract text (or use existing if available)
        if file_info.extracted_text:
            extracted_text = file_info.extracted_text
            results["steps"]["extract"] = {"success": True, "source": "cached", "chars": len(extracted_text)}
        else:
            extraction = processor.extract_text(content, file_info.filename)
            if not extraction["success"]:
                raise HTTPException(status_code=400, detail=extraction.get("error"))
            extracted_text = extraction["text"]
            results["steps"]["extract"] = {
                "success": True,
                "source": "fresh",
                "pages": extraction.get("pages", 1),
                "chars": len(extracted_text)
            }

        # Step 3: Chunk text
        chunks = processor.chunk_text(extracted_text, chunk_size, chunk_overlap)
        results["steps"]["chunk"] = {"success": True, "total_chunks": len(chunks)}

        # Step 4: Generate embeddings
        embedded_chunks = processor.generate_embeddings_batch(chunks)
        success_embeddings = sum(1 for c in embedded_chunks if c.get("embedding"))
        results["steps"]["embed"] = {
            "success": success_embeddings > 0,
            "successful": success_embeddings,
            "failed": len(embedded_chunks) - success_embeddings
        }

        if success_embeddings == 0:
            raise HTTPException(status_code=500, detail="Failed to generate any embeddings")

        # Step 5: Delete existing chunks from OpenSearch
        delete_result = opensearch.delete_document(s3_key)
        results["steps"]["delete_old"] = {
            "success": True,
            "deleted_chunks": delete_result.get("deleted", 0)
        }

        # Step 6: Index new chunks to OpenSearch
        opensearch.create_index(recreate=False)

        indexed_count = 0
        with opensearch._get_client() as client:
            for chunk in embedded_chunks:
                if not chunk.get("embedding"):
                    continue

                doc = {
                    "content": chunk["text"],
                    "content_embedding": chunk["embedding"],
                    "filename": file_info.filename,
                    "s3_key": s3_key,
                    "file_type": file_info.file_type,
                    "chunk_index": chunk["index"],
                    "total_chunks": len(chunks),
                    "indexed_at": datetime.utcnow().isoformat(),
                    "metadata": {
                        "onboarding_method": "reindex",
                        "chunk_size": chunk_size,
                        "chunk_overlap": chunk_overlap,
                        "embedding_provider": chunk.get("embedding_provider", "unknown"),
                        "embedding_model": chunk.get("embedding_model", "unknown")
                    }
                }

                response = client.post(f"/{opensearch.index_name}/_doc?refresh=true", json=doc)
                if response.status_code in [200, 201]:
                    indexed_count += 1

        results["steps"]["index"] = {"success": indexed_count > 0, "indexed": indexed_count}

        # Update database record
        FileRepository.update_status(
            s3_key=s3_key,
            status=ProcessingStatus.COMPLETED,
            processing_type=ProcessingType.INDEXING,
            extracted_text=extracted_text,
            indexed=True
        )

        results["success"] = indexed_count > 0
        results["indexed_chunks"] = indexed_count
        results["message"] = f"Successfully re-indexed '{file_info.filename}' with {indexed_count} chunks"

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return results


@router.get("/files/{s3_key:path}/index-status")
async def get_file_index_status(s3_key: str) -> Dict[str, Any]:
    """
    Check if a file from Files tab is indexed in the knowledge base.
    Returns chunk count and index status.
    """
    opensearch = get_opensearch_service()

    # Get file info from database
    file_info = FileRepository.get_by_s3_key(s3_key)
    if not file_info:
        raise HTTPException(status_code=404, detail=f"File not found: {s3_key}")

    # Check OpenSearch for chunks
    try:
        with opensearch._get_client() as client:
            response = client.post(
                f"/{opensearch.index_name}/_search",
                json={
                    "query": {"term": {"s3_key.keyword": s3_key}},
                    "size": 0,
                    "aggs": {
                        "chunk_count": {"value_count": {"field": "chunk_index"}}
                    }
                }
            )

            if response.status_code == 200:
                result = response.json()
                chunk_count = result.get("aggregations", {}).get("chunk_count", {}).get("value", 0)
            else:
                chunk_count = 0

    except Exception as e:
        chunk_count = 0

    return {
        "s3_key": s3_key,
        "filename": file_info.filename,
        "indexed": file_info.indexed,
        "chunk_count": chunk_count,
        "has_extracted_text": bool(file_info.extracted_text),
        "processing_status": file_info.processing_status.value if file_info.processing_status else None
    }


# ==========================================
# Bulk Recovery / Rebuild from S3
# ==========================================

@router.post("/rebuild-all")
async def rebuild_all_from_s3(
    chunk_size: int = Query(default=1000),
    chunk_overlap: int = Query(default=200),
    skip_indexed: bool = Query(default=True, description="Skip files already indexed in OpenSearch")
) -> Dict[str, Any]:
    """
    Rebuild entire knowledge base from S3 ground truth.
    Processes ONE file at a time to minimize memory usage (container-friendly).

    Steps:
    1. Sync DB from S3 (recover file records)
    2. For each file with extracted text: chunk → embed → index (one at a time)

    Use this when:
    - OpenSearch index is lost/corrupted
    - Local DB is lost (will be rebuilt from S3)
    - Embedding model changed and need to re-embed all
    """
    s3_service = get_s3_service()
    processor = get_document_processor()
    opensearch = get_opensearch_service()

    results = {
        "phase1_sync": {},
        "phase2_index": {
            "processed": 0,
            "indexed": 0,
            "skipped": 0,
            "failed": 0,
            "errors": []
        }
    }

    # Phase 1: Sync database from S3
    try:
        sync_result = s3_service.sync_from_s3()
        results["phase1_sync"] = {
            "success": True,
            "synced": sync_result["synced"],
            "skipped": sync_result["skipped"],
            "total_in_s3": sync_result["total_in_s3"]
        }
    except Exception as e:
        results["phase1_sync"] = {"success": False, "error": str(e)}
        return results

    # Phase 2: Index files one at a time
    # Get all files that have been processed (extracted text exists in S3)
    all_files = FileRepository.get_all()
    files_to_index = [f for f in all_files if f.processing_status == ProcessingStatus.COMPLETED]

    # Ensure index exists
    opensearch.create_index(recreate=False)

    for file_info in files_to_index:
        s3_key = file_info.s3_key

        # Skip if already indexed and skip_indexed=True
        if skip_indexed and file_info.indexed:
            # Verify it's actually in OpenSearch
            try:
                with opensearch._get_client() as client:
                    response = client.post(
                        f"/{opensearch.index_name}/_search",
                        json={"query": {"term": {"s3_key.keyword": s3_key}}, "size": 0}
                    )
                    if response.status_code == 200:
                        hit_count = response.json().get("hits", {}).get("total", {}).get("value", 0)
                        if hit_count > 0:
                            results["phase2_index"]["skipped"] += 1
                            continue
            except:
                pass  # If check fails, proceed to index

        try:
            # Step 0: Load extracted text from S3 on-demand (memory efficient)
            extracted_text = file_info.extracted_text
            if not extracted_text:
                # Try to load from S3
                base_key = s3_key.rsplit('.', 1)[0] if '.' in s3_key else s3_key
                for ext in ['txt', 'json', 'md']:
                    extracted_key = f"{base_key}_extracted.{ext}"
                    try:
                        extracted_text = s3_service.get_file_content(extracted_key).decode('utf-8')
                        break
                    except:
                        continue

            if not extracted_text:
                results["phase2_index"]["failed"] += 1
                results["phase2_index"]["errors"].append(f"{file_info.filename}: No extracted text found")
                continue

            # Step 1: Chunk text
            chunks = processor.chunk_text(extracted_text, chunk_size, chunk_overlap)

            # Step 2: Generate embeddings (one batch per file)
            embedded_chunks = processor.generate_embeddings_batch(chunks)
            success_embeddings = sum(1 for c in embedded_chunks if c.get("embedding"))

            if success_embeddings == 0:
                results["phase2_index"]["failed"] += 1
                results["phase2_index"]["errors"].append(f"{file_info.filename}: No embeddings generated")
                continue

            # Step 3: Delete existing chunks (if any)
            opensearch.delete_document(s3_key)

            # Step 4: Index chunks one by one
            indexed_count = 0
            with opensearch._get_client() as client:
                for chunk in embedded_chunks:
                    if not chunk.get("embedding"):
                        continue

                    doc = {
                        "content": chunk["text"],
                        "content_embedding": chunk["embedding"],
                        "filename": file_info.filename,
                        "s3_key": s3_key,
                        "file_type": file_info.file_type,
                        "chunk_index": chunk["index"],
                        "total_chunks": len(chunks),
                        "indexed_at": datetime.utcnow().isoformat(),
                        "metadata": {
                            "onboarding_method": "rebuild",
                            "chunk_size": chunk_size,
                            "chunk_overlap": chunk_overlap
                        }
                    }

                    response = client.post(f"/{opensearch.index_name}/_doc?refresh=true", json=doc)
                    if response.status_code in [200, 201]:
                        indexed_count += 1

            # Update DB record
            if indexed_count > 0:
                FileRepository.update_status(
                    s3_key=s3_key,
                    status=ProcessingStatus.COMPLETED,
                    processing_type=ProcessingType.INDEXING,
                    indexed=True
                )
                results["phase2_index"]["indexed"] += 1
            else:
                results["phase2_index"]["failed"] += 1

            results["phase2_index"]["processed"] += 1

            # Clear references to free memory before next file
            del chunks
            del embedded_chunks
            del extracted_text

        except Exception as e:
            results["phase2_index"]["failed"] += 1
            results["phase2_index"]["errors"].append(f"{file_info.filename}: {str(e)}")

    results["success"] = results["phase2_index"]["failed"] == 0
    results["message"] = (
        f"Rebuilt KB: {results['phase2_index']['indexed']} indexed, "
        f"{results['phase2_index']['skipped']} skipped, "
        f"{results['phase2_index']['failed']} failed"
    )

    return results
