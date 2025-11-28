import boto3
from datetime import datetime
from typing import List, Optional
from botocore.exceptions import ClientError
from fastapi import UploadFile

from ..config import get_settings
from ..models.schemas import FileInfo, ProcessingStatus, ProcessingType
from ..database import FileRepository


class S3Service:
    def __init__(self):
        self.settings = get_settings()

        # Use explicit credentials if provided, otherwise use default credential chain
        # (environment variables, ~/.aws/credentials, IAM role, etc.)
        if self.settings.AWS_ACCESS_KEY_ID and self.settings.AWS_SECRET_ACCESS_KEY:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=self.settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=self.settings.AWS_SECRET_ACCESS_KEY,
                region_name=self.settings.AWS_REGION
            )
        else:
            # Use default credential chain (local credentials)
            self.s3_client = boto3.client(
                's3',
                region_name=self.settings.AWS_REGION
            )

        self.bucket_name = self.settings.S3_BUCKET_NAME
        self.folder_prefix = self.settings.S3_FOLDER_PREFIX

    def _get_file_extension(self, filename: str) -> str:
        """Get file extension from filename"""
        return filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''

    async def upload_file(self, file: UploadFile) -> FileInfo:
        """Upload file to S3 and store metadata in database"""
        settings = get_settings()

        # Validate file extension
        file_ext = self._get_file_extension(file.filename)
        if file_ext not in settings.ALLOWED_EXTENSIONS:
            raise ValueError(f"File type .{file_ext} not allowed. Allowed types: {settings.ALLOWED_EXTENSIONS}")

        # Read file content
        content = await file.read()
        file_size = len(content)

        # Check file size
        max_size = settings.MAX_FILE_SIZE_MB * 1024 * 1024
        if file_size > max_size:
            raise ValueError(f"File size exceeds maximum allowed size of {settings.MAX_FILE_SIZE_MB}MB")

        # Generate S3 key with timestamp to avoid conflicts
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        s3_key = f"{self.folder_prefix}{timestamp}_{file.filename}"

        # Determine content type
        content_types = {
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'pdf': 'application/pdf',
            'txt': 'text/plain',
            'json': 'application/json'
        }
        content_type = content_types.get(file_ext, 'application/octet-stream')

        # Upload to S3
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=content,
                ContentType=content_type
            )
        except ClientError as e:
            raise Exception(f"Failed to upload to S3: {str(e)}")

        # Store metadata in database
        upload_time = datetime.now()
        file_info = FileInfo(
            filename=file.filename,
            s3_key=s3_key,
            file_type=file_ext,
            size=file_size,
            upload_time=upload_time,
            processing_status=ProcessingStatus.PENDING,
            processing_type=None,
            processed_at=None,
            extracted_text=None,
            indexed=False
        )

        FileRepository.create(file_info)
        return file_info

    def list_files(self) -> List[FileInfo]:
        """List all uploaded files with their processing status from database"""
        return FileRepository.get_all()

    def get_file_info(self, s3_key: str) -> Optional[FileInfo]:
        """Get file info by S3 key from database"""
        return FileRepository.get_by_s3_key(s3_key)

    def update_file_status(
        self,
        s3_key: str,
        status: ProcessingStatus,
        processing_type: Optional[ProcessingType] = None,
        extracted_text: Optional[str] = None,
        indexed: bool = False
    ):
        """Update file processing status in database"""
        file_info = FileRepository.get_by_s3_key(s3_key)
        if not file_info:
            raise ValueError(f"File not found: {s3_key}")

        FileRepository.update_status(
            s3_key=s3_key,
            status=status,
            processing_type=processing_type,
            extracted_text=extracted_text,
            indexed=indexed
        )

    def get_file_content(self, s3_key: str) -> bytes:
        """Download file content from S3"""
        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            return response['Body'].read()
        except ClientError as e:
            raise Exception(f"Failed to download from S3: {str(e)}")

    def delete_file(self, s3_key: str):
        """Delete file from S3 and database"""
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
        except ClientError as e:
            raise Exception(f"Failed to delete from S3: {str(e)}")

        FileRepository.delete(s3_key)

    def list_s3_files(self) -> List[dict]:
        """List all files in S3 bucket under the folder prefix (returns list for backward compatibility)"""
        return list(self.iter_s3_files())

    def iter_s3_files(self):
        """Generator to iterate S3 files one page at a time (memory efficient)"""
        try:
            paginator = self.s3_client.get_paginator('list_objects_v2')
            for page in paginator.paginate(Bucket=self.bucket_name, Prefix=self.folder_prefix):
                for obj in page.get('Contents', []):
                    s3_key = obj['Key']
                    # Skip folder markers and extracted files
                    if s3_key.endswith('/') or '_extracted.' in s3_key:
                        continue

                    yield {
                        's3_key': s3_key,
                        'size': obj['Size'],
                        'last_modified': obj['LastModified']
                    }
        except ClientError as e:
            raise Exception(f"Failed to list S3 files: {str(e)}")

    def sync_from_s3(self) -> dict:
        """Sync database with files from S3 (recover database from S3 ground truth)
        Uses generator to process files one at a time (memory efficient for containers)
        """
        settings = get_settings()

        synced = 0
        skipped = 0
        total_scanned = 0
        errors = []

        # Use generator - processes one file at a time, not all at once
        for s3_file in self.iter_s3_files():
            total_scanned += 1
            s3_key = s3_file['s3_key']

            # Check if file already exists in database
            existing = FileRepository.get_by_s3_key(s3_key)
            if existing:
                skipped += 1
                continue

            try:
                # Extract filename from s3_key (remove prefix and timestamp)
                # Format 1: uploads/20241125_123456_filename.ext (regular upload)
                # Format 2: uploads/kb_20241125_123456_hash_filename.ext (KB onboard)
                filename = s3_key.replace(self.folder_prefix, '')

                # Check if it's a KB file (starts with kb_)
                if filename.startswith('kb_'):
                    # Format: kb_timestamp_hash_filename.ext
                    parts = filename.split('_', 3)  # Split into max 4 parts
                    if len(parts) >= 4:
                        filename = parts[3]  # Get the original filename
                    elif len(parts) == 3:
                        filename = parts[2]  # Fallback
                else:
                    # Regular format: timestamp_filename.ext
                    parts = filename.split('_', 2)  # Split into max 3 parts
                    if len(parts) >= 3:
                        filename = parts[2]  # Get the original filename
                    elif len(parts) == 2:
                        filename = parts[1]  # Fallback

                file_ext = self._get_file_extension(filename)

                # Skip unsupported file types
                if file_ext not in settings.ALLOWED_EXTENSIONS:
                    skipped += 1
                    continue

                # Check if there's an extracted file for this (metadata only, don't load content)
                base_key = s3_key.rsplit('.', 1)[0] if '.' in s3_key else s3_key
                has_extracted = False
                extracted_s3_key = None

                # Try to find extracted file (just check existence, don't download)
                for ext in ['txt', 'json', 'md']:
                    extracted_key = f"{base_key}_extracted.{ext}"
                    try:
                        self.s3_client.head_object(
                            Bucket=self.bucket_name,
                            Key=extracted_key
                        )
                        has_extracted = True
                        extracted_s3_key = extracted_key
                        break
                    except ClientError:
                        continue

                # Create file info (no extracted_text - will be loaded on-demand during indexing)
                file_info = FileInfo(
                    filename=filename,
                    s3_key=s3_key,
                    file_type=file_ext,
                    size=s3_file['size'],
                    upload_time=s3_file['last_modified'],
                    processing_status=ProcessingStatus.COMPLETED if has_extracted else ProcessingStatus.PENDING,
                    processing_type=ProcessingType.LLM_EXTRACT if has_extracted else None,
                    processed_at=datetime.now() if has_extracted else None,
                    extracted_text=None,  # Don't load - save memory
                    indexed=False
                )

                FileRepository.create(file_info)
                synced += 1

            except Exception as e:
                errors.append(f"{s3_key}: {str(e)}")

        return {
            "synced": synced,
            "skipped": skipped,
            "errors": errors,
            "total_in_s3": total_scanned
        }

    def save_extracted_text(self, original_s3_key: str, extracted_text: str, output_format: str = "text") -> str:
        """Save extracted text to S3 as a new file"""
        # Determine file extension based on output format
        ext_map = {
            "text": "txt",
            "json": "json",
            "markdown": "md"
        }
        file_ext = ext_map.get(output_format, "txt")

        # Generate new S3 key for extracted content
        # Replace original extension with _extracted.{ext}
        base_key = original_s3_key.rsplit('.', 1)[0] if '.' in original_s3_key else original_s3_key
        extracted_s3_key = f"{base_key}_extracted.{file_ext}"

        # Determine content type
        content_types = {
            "txt": "text/plain",
            "json": "application/json",
            "md": "text/markdown"
        }
        content_type = content_types.get(file_ext, "text/plain")

        # Upload extracted text to S3
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=extracted_s3_key,
                Body=extracted_text.encode('utf-8'),
                ContentType=content_type
            )
        except ClientError as e:
            raise Exception(f"Failed to save extracted text to S3: {str(e)}")

        return extracted_s3_key


# Singleton instance
_s3_service: Optional[S3Service] = None


def get_s3_service() -> S3Service:
    global _s3_service
    if _s3_service is None:
        _s3_service = S3Service()
    return _s3_service
