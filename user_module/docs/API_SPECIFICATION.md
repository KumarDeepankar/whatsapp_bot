# API Specification

> RESTful API documentation for the User Module Knowledge Base service.

---

## Overview

| Property | Value |
|----------|-------|
| **Base URL** | `http://localhost:8000` |
| **API Prefix** | `/api/knowledge-base` |
| **Authentication** | Session-based (Cookie) |
| **Content-Type** | `application/json`, `multipart/form-data` |

---

## Table of Contents

1. [Authentication](#1-authentication)
2. [Status & Health](#2-status--health)
3. [Document Onboarding](#3-document-onboarding)
4. [Index Management](#4-index-management)
5. [Document Management](#5-document-management)
6. [Search](#6-search)
7. [Error Handling](#7-error-handling)
8. [Data Types](#8-data-types)

---

## 1. Authentication

### Login

```http
POST /api/auth/login
```

**Request Body** (`application/x-www-form-urlencoded`):

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `username` | string | Yes | Username |
| `password` | string | Yes | Password |

**Response** `200 OK`:
```json
{
  "success": true,
  "message": "Login successful"
}
```

**Response** `401 Unauthorized`:
```json
{
  "detail": "Invalid credentials"
}
```

---

## 2. Status & Health

### Get System Status

```http
GET /api/knowledge-base/status
```

Returns OpenSearch connection status, index statistics, and embedding provider info.

**Response** `200 OK`:
```json
{
  "connected": true,
  "cluster_name": "opensearch-cluster",
  "version": "2.11.0",
  "index": {
    "name": "whatsapp_knowledge_base",
    "exists": true,
    "total_chunks": 150,
    "unique_documents": 5,
    "size_mb": 2.5
  },
  "embedding": {
    "configured": true,
    "provider": "Google Gemini",
    "model": "models/text-embedding-004",
    "dimensions": 768
  }
}
```

**Response** (OpenSearch disconnected):
```json
{
  "connected": false,
  "error": "Connection refused",
  "embedding": {
    "configured": true,
    "provider": "Ollama (Local)",
    "model": "nomic-embed-text",
    "dimensions": 768
  }
}
```

---

### Get Embedding Provider Status

```http
GET /api/knowledge-base/embedding/status
```

Returns detailed health check for all embedding providers.

**Response** `200 OK`:
```json
{
  "current_provider": {
    "configured": true,
    "provider": "Ollama (Local)",
    "model": "nomic-embed-text",
    "dimensions": 768
  },
  "available_providers": {
    "gemini": {
      "available": false,
      "provider": "Google Gemini",
      "model": "models/text-embedding-004",
      "error": "GOOGLE_API_KEY not configured"
    },
    "ollama": {
      "available": true,
      "provider": "Ollama (Local)",
      "model": "nomic-embed-text",
      "dimensions": 768,
      "available_models": ["nomic-embed-text", "llama2", "mistral"]
    }
  }
}
```

---

## 3. Document Onboarding

### Step 1: Upload & Validate

```http
POST /api/knowledge-base/onboard/step1-upload
```

**Request** (`multipart/form-data`):

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | file | Yes | Document file (PDF, TXT, JSON, JPG, PNG) |

**Response** `200 OK`:
```json
{
  "success": true,
  "step": 1,
  "filename": "product_catalog.pdf",
  "file_type": "pdf",
  "file_size": 1048576,
  "file_size_formatted": "1.0 MB",
  "content_b64": "JVBERi0xLjQKJe...",
  "message": "File 'product_catalog.pdf' uploaded and validated successfully"
}
```

**Response** `400 Bad Request`:
```json
{
  "detail": "Unsupported file type: .doc. Supported: pdf, txt, json, jpg, jpeg, png"
}
```

---

### Step 2: Extract Text

```http
POST /api/knowledge-base/onboard/step2-extract
```

**Request** (`multipart/form-data`):

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `filename` | string | Yes | Original filename |
| `content_b64` | string | Yes | Base64-encoded file content from Step 1 |

**Response** `200 OK`:
```json
{
  "success": true,
  "step": 2,
  "filename": "product_catalog.pdf",
  "text": "Full extracted text content...",
  "pages": 10,
  "total_chars": 45000,
  "total_words": 7500,
  "preview": "First 500 characters of text...",
  "message": "Extracted 45,000 characters from 10 page(s)"
}
```

---

### Step 3: Chunk Text

```http
POST /api/knowledge-base/onboard/step3-chunk
```

**Request** (`multipart/form-data`):

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `filename` | string | Yes | - | Original filename |
| `text` | string | Yes | - | Extracted text from Step 2 |
| `chunk_size` | integer | No | 1000 | Characters per chunk (100-5000) |
| `chunk_overlap` | integer | No | 200 | Overlap between chunks |

**Response** `200 OK`:
```json
{
  "success": true,
  "step": 3,
  "filename": "product_catalog.pdf",
  "chunks": [
    {
      "index": 0,
      "text": "Chunk text content...",
      "chars": 985,
      "start": 0,
      "end": 985
    }
  ],
  "chunks_preview": [
    {
      "index": 0,
      "preview": "First 200 chars of chunk...",
      "chars": 985
    }
  ],
  "stats": {
    "total_chars": 45000,
    "total_words": 7500,
    "total_chunks": 50,
    "avg_chunk_size": 900,
    "min_chunk_size": 450,
    "max_chunk_size": 1000
  },
  "config": {
    "chunk_size": 1000,
    "chunk_overlap": 200
  },
  "message": "Created 50 chunks (avg 900 chars each)"
}
```

---

### Step 4: Generate Embeddings

```http
POST /api/knowledge-base/onboard/step4-embed
```

**Request** (`multipart/form-data`):

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `filename` | string | Yes | Original filename |
| `chunks_json` | string | Yes | JSON stringified chunks array from Step 3 |

**Response** `200 OK`:
```json
{
  "success": true,
  "step": 4,
  "filename": "product_catalog.pdf",
  "chunks": [
    {
      "index": 0,
      "text": "Chunk text...",
      "chars": 985,
      "embedding": [0.0123, -0.0456, ...],
      "embedding_status": "success",
      "embedding_provider": "Ollama (Local)",
      "embedding_model": "nomic-embed-text"
    }
  ],
  "total_chunks": 50,
  "successful": 50,
  "failed": 0,
  "embedding_dimension": 768,
  "message": "Generated embeddings for 50/50 chunks"
}
```

---

### Step 5: Index to OpenSearch

```http
POST /api/knowledge-base/onboard/step5-index
```

**Request** (`multipart/form-data`):

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `filename` | string | Yes | Original filename |
| `file_type` | string | Yes | File extension (pdf, txt, etc.) |
| `chunks_json` | string | Yes | JSON stringified embedded chunks from Step 4 |
| `metadata_json` | string | No | Additional metadata (default: "{}") |

**Response** `200 OK`:
```json
{
  "success": true,
  "step": 5,
  "filename": "product_catalog.pdf",
  "s3_key": "kb_direct/20241126_143022_a1b2c3d4/product_catalog.pdf",
  "indexed_chunks": 50,
  "total_chunks": 50,
  "failed_chunks": 0,
  "doc_ids": ["abc123", "def456", ...],
  "errors": null,
  "message": "Successfully indexed 50/50 chunks to knowledge base"
}
```

---

### Full Onboarding (One-Click)

```http
POST /api/knowledge-base/onboard/full
```

Combines all 5 steps in a single request.

**Request** (`multipart/form-data`):

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `file` | file | Yes | - | Document file |
| `chunk_size` | integer | No | 1000 | Characters per chunk |
| `chunk_overlap` | integer | No | 200 | Overlap between chunks |

**Response** `200 OK`:
```json
{
  "filename": "product_catalog.pdf",
  "success": true,
  "s3_key": "kb_direct/20241126_143022_a1b2c3d4/product_catalog.pdf",
  "steps": {
    "upload": { "success": true, "file_size": 1048576 },
    "extract": { "success": true, "pages": 10, "chars": 45000 },
    "chunk": { "success": true, "total_chunks": 50 },
    "embed": { "success": true, "successful": 50, "failed": 0 },
    "index": { "success": true, "indexed": 50 }
  },
  "message": "Successfully onboarded 'product_catalog.pdf' with 50 chunks"
}
```

---

## 4. Index Management

### Create Index

```http
POST /api/knowledge-base/index/create
```

**Query Parameters**:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `recreate` | boolean | false | If true, deletes existing index first |

**Response** `200 OK`:
```json
{
  "success": true,
  "message": "Index 'whatsapp_knowledge_base' created successfully",
  "index_name": "whatsapp_knowledge_base"
}
```

**Response** (already exists):
```json
{
  "success": true,
  "message": "Index 'whatsapp_knowledge_base' already exists",
  "index_name": "whatsapp_knowledge_base"
}
```

---

### Delete Index

```http
DELETE /api/knowledge-base/index
```

**Response** `200 OK`:
```json
{
  "success": true,
  "message": "Index 'whatsapp_knowledge_base' deleted successfully"
}
```

---

## 5. Document Management

### List Indexed Documents

```http
GET /api/knowledge-base/documents
```

**Response** `200 OK`:
```json
{
  "documents": [
    {
      "filename": "product_catalog.pdf",
      "s3_key": "kb_direct/20241126_143022_a1b2c3d4/product_catalog.pdf",
      "file_type": "pdf",
      "chunk_count": 50,
      "indexed_at": "2024-11-26T14:30:22.000Z"
    },
    {
      "filename": "faq.txt",
      "s3_key": "kb_direct/20241125_093015_e5f6g7h8/faq.txt",
      "file_type": "txt",
      "chunk_count": 12,
      "indexed_at": "2024-11-25T09:30:15.000Z"
    }
  ],
  "total": 2
}
```

---

### Remove Document

```http
DELETE /api/knowledge-base/documents/{s3_key}
```

**Path Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `s3_key` | string | URL-encoded document identifier |

**Example**:
```http
DELETE /api/knowledge-base/documents/kb_direct%2F20241126_143022_a1b2c3d4%2Fproduct_catalog.pdf
```

**Response** `200 OK`:
```json
{
  "success": true,
  "message": "Removed document from knowledge base",
  "deleted_chunks": 50
}
```

---

## 6. Search

### Search Knowledge Base (GET)

```http
GET /api/knowledge-base/search
```

**Query Parameters**:

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | string | Yes | - | Search query (min 1 char) |
| `k` | integer | No | 5 | Number of results (1-20) |
| `use_hybrid` | boolean | No | true | Use hybrid search (vector + text) |

**Example**:
```http
GET /api/knowledge-base/search?query=product%20price&k=5&use_hybrid=true
```

**Response** `200 OK`:
```json
{
  "query": "product price",
  "results": [
    {
      "content": "The Rustoline 4x12 hinge is priced at 109/- per piece...",
      "filename": "product_catalog.pdf",
      "s3_key": "kb_direct/20241126_143022_a1b2c3d4/product_catalog.pdf",
      "file_type": "pdf",
      "chunk_index": 15,
      "score": 0.8956
    },
    {
      "content": "Ball bearing slides range from 250/- to 450/-...",
      "filename": "product_catalog.pdf",
      "s3_key": "kb_direct/20241126_143022_a1b2c3d4/product_catalog.pdf",
      "file_type": "pdf",
      "chunk_index": 22,
      "score": 0.8234
    }
  ],
  "total_results": 2
}
```

---

### Search Knowledge Base (POST)

```http
POST /api/knowledge-base/search
```

**Request** (`multipart/form-data`):

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `query` | string | Yes | - | Search query |
| `k` | integer | No | 5 | Number of results |

**Response**: Same as GET method.

---

## 7. Error Handling

### Error Response Format

All errors follow this structure:

```json
{
  "detail": "Error message describing what went wrong"
}
```

### HTTP Status Codes

| Code | Meaning | Common Causes |
|------|---------|---------------|
| `200` | Success | Request completed successfully |
| `400` | Bad Request | Invalid input, validation error |
| `401` | Unauthorized | Not logged in, session expired |
| `404` | Not Found | Resource doesn't exist |
| `500` | Internal Server Error | Server-side error, service unavailable |

### Common Errors

**Unsupported File Type**:
```json
{
  "detail": "Unsupported file type: .doc. Supported: pdf, txt, json, jpg, jpeg, png"
}
```

**File Too Large**:
```json
{
  "detail": "File too large. Maximum: 50MB"
}
```

**Embedding Provider Not Configured**:
```json
{
  "detail": "Embedding provider not configured. Set EMBEDDING_PROVIDER and required API keys in .env"
}
```

**OpenSearch Connection Failed**:
```json
{
  "detail": "OpenSearch connection failed: Connection refused"
}
```

**Ollama Model Not Found**:
```json
{
  "detail": "Model 'nomic-embed-text' not found. Pull it first: `ollama pull nomic-embed-text`"
}
```

---

## 8. Data Types

### Chunk Object

```typescript
interface Chunk {
  index: number;        // Position in document (0-based)
  text: string;         // Chunk content
  chars: number;        // Character count
  start: number;        // Start position in original text
  end: number;          // End position in original text
}
```

### Embedded Chunk Object

```typescript
interface EmbeddedChunk extends Chunk {
  embedding: number[] | null;     // 768-dimensional vector
  embedding_status: "success" | "failed";
  embedding_provider?: string;    // e.g., "Ollama (Local)"
  embedding_model?: string;       // e.g., "nomic-embed-text"
  embedding_error?: string;       // Error message if failed
}
```

### Document Object

```typescript
interface Document {
  filename: string;           // Original filename
  s3_key: string;             // Unique identifier
  file_type: string;          // pdf, txt, json, jpg, png
  chunk_count: number;        // Number of chunks
  indexed_at: string;         // ISO 8601 timestamp
}
```

### Search Result Object

```typescript
interface SearchResult {
  content: string;            // Chunk text
  filename: string;           // Source document
  s3_key: string;             // Document identifier
  file_type: string;          // File type
  chunk_index: number;        // Chunk position
  score: number;              // Relevance score (0-1)
}
```

### Embedding Info Object

```typescript
interface EmbeddingInfo {
  configured: boolean;        // Whether provider is ready
  provider?: string;          // Provider name
  model?: string;             // Model identifier
  dimensions?: number;        // Vector dimensions
  error?: string;             // Error if not configured
}
```

---

## Quick Reference

### Endpoints Summary

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/knowledge-base/status` | System status |
| `GET` | `/api/knowledge-base/embedding/status` | Embedding provider status |
| `POST` | `/api/knowledge-base/onboard/step1-upload` | Upload & validate |
| `POST` | `/api/knowledge-base/onboard/step2-extract` | Extract text |
| `POST` | `/api/knowledge-base/onboard/step3-chunk` | Chunk text |
| `POST` | `/api/knowledge-base/onboard/step4-embed` | Generate embeddings |
| `POST` | `/api/knowledge-base/onboard/step5-index` | Index to OpenSearch |
| `POST` | `/api/knowledge-base/onboard/full` | Full onboarding |
| `POST` | `/api/knowledge-base/index/create` | Create index |
| `DELETE` | `/api/knowledge-base/index` | Delete index |
| `GET` | `/api/knowledge-base/documents` | List documents |
| `DELETE` | `/api/knowledge-base/documents/{s3_key}` | Remove document |
| `GET` | `/api/knowledge-base/search` | Search KB |
| `POST` | `/api/knowledge-base/search` | Search KB (POST) |

---

## cURL Examples

### Full Onboarding
```bash
curl -X POST http://localhost:8000/api/knowledge-base/onboard/full \
  -F "file=@document.pdf" \
  -F "chunk_size=1000" \
  -F "chunk_overlap=200"
```

### Search
```bash
curl "http://localhost:8000/api/knowledge-base/search?query=product%20price&k=5"
```

### Check Status
```bash
curl http://localhost:8000/api/knowledge-base/status
```

### Delete Document
```bash
curl -X DELETE "http://localhost:8000/api/knowledge-base/documents/kb_direct%2F20241126%2Fdoc.pdf"
```

---

*Last Updated: November 2024*
