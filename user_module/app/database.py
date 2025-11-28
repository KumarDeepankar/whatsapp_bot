import sqlite3
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime
from typing import Optional, List
import json

from .models.schemas import FileInfo, ProcessingStatus, ProcessingType

# Database file path
DB_PATH = Path(__file__).parent.parent / "user_module.db"


def get_db_connection():
    """Get a database connection with row factory"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def get_db():
    """Context manager for database connections"""
    conn = get_db_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Initialize the database schema"""
    with get_db() as conn:
        cursor = conn.cursor()

        # Create files table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                s3_key TEXT UNIQUE NOT NULL,
                file_type TEXT NOT NULL,
                size INTEGER NOT NULL,
                upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processing_status TEXT DEFAULT 'pending',
                processing_type TEXT,
                processed_at TIMESTAMP,
                extracted_text TEXT,
                indexed INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create index on s3_key for faster lookups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_files_s3_key ON files(s3_key)
        """)

        # Create index on processing_status for filtering
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_files_status ON files(processing_status)
        """)

        # Create text index table for search functionality
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS text_index (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id INTEGER NOT NULL,
                s3_key TEXT NOT NULL,
                content TEXT,
                word_count INTEGER,
                char_count INTEGER,
                indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE
            )
        """)

        # Create FTS5 virtual table for full-text search
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS files_fts USING fts5(
                filename,
                extracted_text,
                content='files',
                content_rowid='id'
            )
        """)

        # Create triggers to keep FTS index in sync
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS files_ai AFTER INSERT ON files BEGIN
                INSERT INTO files_fts(rowid, filename, extracted_text)
                VALUES (new.id, new.filename, new.extracted_text);
            END
        """)

        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS files_ad AFTER DELETE ON files BEGIN
                INSERT INTO files_fts(files_fts, rowid, filename, extracted_text)
                VALUES ('delete', old.id, old.filename, old.extracted_text);
            END
        """)

        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS files_au AFTER UPDATE ON files BEGIN
                INSERT INTO files_fts(files_fts, rowid, filename, extracted_text)
                VALUES ('delete', old.id, old.filename, old.extracted_text);
                INSERT INTO files_fts(rowid, filename, extracted_text)
                VALUES (new.id, new.filename, new.extracted_text);
            END
        """)


class FileRepository:
    """Repository for file database operations"""

    @staticmethod
    def create(file_info: FileInfo) -> FileInfo:
        """Insert a new file record"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO files (filename, s3_key, file_type, size, upload_time,
                                   processing_status, processing_type, extracted_text, indexed)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                file_info.filename,
                file_info.s3_key,
                file_info.file_type,
                file_info.size,
                file_info.upload_time.isoformat(),
                file_info.processing_status.value,
                file_info.processing_type.value if file_info.processing_type else None,
                file_info.extracted_text,
                1 if file_info.indexed else 0
            ))
        return file_info

    @staticmethod
    def get_by_s3_key(s3_key: str) -> Optional[FileInfo]:
        """Get a file by its S3 key"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM files WHERE s3_key = ?", (s3_key,))
            row = cursor.fetchone()

            if not row:
                return None

            return FileRepository._row_to_file_info(row)

    @staticmethod
    def get_all() -> List[FileInfo]:
        """Get all files ordered by upload time descending"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM files ORDER BY upload_time DESC")
            rows = cursor.fetchall()

            return [FileRepository._row_to_file_info(row) for row in rows]

    @staticmethod
    def update_status(
        s3_key: str,
        status: ProcessingStatus,
        processing_type: Optional[ProcessingType] = None,
        extracted_text: Optional[str] = None,
        indexed: bool = False
    ):
        """Update file processing status"""
        with get_db() as conn:
            cursor = conn.cursor()

            updates = ["processing_status = ?", "updated_at = ?"]
            params = [status.value, datetime.now().isoformat()]

            if processing_type:
                updates.append("processing_type = ?")
                params.append(processing_type.value)

            if status == ProcessingStatus.COMPLETED:
                updates.append("processed_at = ?")
                params.append(datetime.now().isoformat())

            if extracted_text is not None:
                updates.append("extracted_text = ?")
                params.append(extracted_text)

            updates.append("indexed = ?")
            params.append(1 if indexed else 0)

            params.append(s3_key)

            cursor.execute(f"""
                UPDATE files SET {', '.join(updates)} WHERE s3_key = ?
            """, params)

    @staticmethod
    def delete(s3_key: str):
        """Delete a file record"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM files WHERE s3_key = ?", (s3_key,))

    @staticmethod
    def _row_to_file_info(row: sqlite3.Row) -> FileInfo:
        """Convert a database row to FileInfo"""
        return FileInfo(
            filename=row["filename"],
            s3_key=row["s3_key"],
            file_type=row["file_type"],
            size=row["size"],
            upload_time=datetime.fromisoformat(row["upload_time"]) if row["upload_time"] else datetime.now(),
            processing_status=ProcessingStatus(row["processing_status"]) if row["processing_status"] else ProcessingStatus.PENDING,
            processing_type=ProcessingType(row["processing_type"]) if row["processing_type"] else None,
            processed_at=datetime.fromisoformat(row["processed_at"]) if row["processed_at"] else None,
            extracted_text=row["extracted_text"],
            indexed=bool(row["indexed"])
        )


# Initialize database on module import
init_db()
