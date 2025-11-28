# Architecture Documentation

> System design, class diagrams, and component relationships for the User Module.

---

## Table of Contents

1. [System Context](#1-system-context)
2. [Container Diagram](#2-container-diagram)
3. [Component Diagram](#3-component-diagram)
4. [Class Diagrams](#4-class-diagrams)
5. [Data Models](#5-data-models)
6. [Sequence Diagrams](#6-sequence-diagrams)
7. [Technology Stack](#7-technology-stack)

---

## 1. System Context

High-level view showing how User Module fits in the overall system.

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                   SYSTEM CONTEXT                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘

                                    ┌─────────────┐
                                    │    Admin    │
                                    │    User     │
                                    └──────┬──────┘
                                           │
                                           │ Manages KB
                                           ▼
┌──────────────────┐              ┌─────────────────┐              ┌──────────────────┐
│                  │              │                 │              │                  │
│  WhatsApp User   │─────────────>│   WhatsApp-     │<─────────────│   User Module    │
│                  │   Messages   │     Main        │   Queries    │  (Admin Portal)  │
│                  │<─────────────│   (Chat Bot)    │   Vectors    │                  │
│                  │   Responses  │                 │              │                  │
└──────────────────┘              └────────┬────────┘              └────────┬─────────┘
                                           │                                │
                                           │                                │
                                           ▼                                ▼
                                  ┌─────────────────────────────────────────────────┐
                                  │                                                 │
                                  │              OpenSearch Cluster                 │
                                  │         (Vector Storage & Search)               │
                                  │                                                 │
                                  └─────────────────────────────────────────────────┘
                                                        ▲
                                                        │
                                  ┌─────────────────────┴─────────────────────┐
                                  │                                           │
                                  ▼                                           ▼
                         ┌─────────────────┐                        ┌─────────────────┐
                         │  Google Gemini  │                        │     Ollama      │
                         │   (Cloud API)   │                        │    (Local)      │
                         │   Embeddings    │                        │   Embeddings    │
                         └─────────────────┘                        └─────────────────┘
```

---

## 2. Container Diagram

Zoomed into the User Module showing major containers.

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              USER MODULE - CONTAINERS                                │
└─────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                    User Module                                       │
│                                                                                     │
│  ┌───────────────────────────────────────────────────────────────────────────────┐  │
│  │                           WEB APPLICATION (FastAPI)                            │  │
│  │                                                                               │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │  │
│  │  │   Auth      │  │   Files     │  │  Knowledge  │  │   Static Assets     │  │  │
│  │  │   Router    │  │   Router    │  │  Base Router│  │   (HTML/CSS/JS)     │  │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────────┘  │  │
│  │         │                │                │                                   │  │
│  │         └────────────────┼────────────────┘                                   │  │
│  │                          ▼                                                    │  │
│  │  ┌───────────────────────────────────────────────────────────────────────┐   │  │
│  │  │                         SERVICE LAYER                                  │   │  │
│  │  │                                                                       │   │  │
│  │  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐   │   │  │
│  │  │  │   Document      │  │   Embedding     │  │    OpenSearch       │   │   │  │
│  │  │  │   Processor     │  │   Providers     │  │    Service          │   │   │  │
│  │  │  └─────────────────┘  └─────────────────┘  └─────────────────────┘   │   │  │
│  │  │                                                                       │   │  │
│  │  └───────────────────────────────────────────────────────────────────────┘   │  │
│  │                                                                               │  │
│  └───────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
         │                              │                              │
         ▼                              ▼                              ▼
┌─────────────────┐          ┌─────────────────┐          ┌─────────────────────────┐
│    SQLite DB    │          │   OpenSearch    │          │   Embedding Provider    │
│  (File Metadata)│          │  (Vector Store) │          │   (Gemini / Ollama)     │
└─────────────────┘          └─────────────────┘          └─────────────────────────┘
```

---

## 3. Component Diagram

Detailed view of components within the service layer.

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                            SERVICE LAYER - COMPONENTS                                │
└─────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │                         DocumentProcessor                                    │   │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐   │   │
│  │  │   PDF       │ │   Text      │ │   JSON      │ │   Image (OCR)       │   │   │
│  │  │  Extractor  │ │  Extractor  │ │  Extractor  │ │   Extractor         │   │   │
│  │  │  (PyMuPDF)  │ │  (decode)   │ │  (json)     │ │   (Gemini Vision)   │   │   │
│  │  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────────────┘   │   │
│  │                          │                                                  │   │
│  │                          ▼                                                  │   │
│  │                 ┌─────────────────┐                                         │   │
│  │                 │   TextChunker   │                                         │   │
│  │                 │  (Recursive)    │                                         │   │
│  │                 └────────┬────────┘                                         │   │
│  │                          │                                                  │   │
│  └──────────────────────────┼──────────────────────────────────────────────────┘   │
│                             │                                                       │
│                             ▼                                                       │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │                      EmbeddingProviderFactory                                │   │
│  │                                                                             │   │
│  │         ┌──────────────────────┐    ┌──────────────────────┐               │   │
│  │         │  GeminiEmbedding     │    │  OllamaEmbedding     │               │   │
│  │         │     Provider         │    │     Provider         │               │   │
│  │         │  ┌────────────────┐  │    │  ┌────────────────┐  │               │   │
│  │         │  │ • Cloud API    │  │    │  │ • Local HTTP   │  │               │   │
│  │         │  │ • 768 dims     │  │    │  │ • Configurable │  │               │   │
│  │         │  │ • Fast         │  │    │  │ • Free         │  │               │   │
│  │         │  └────────────────┘  │    │  └────────────────┘  │               │   │
│  │         └──────────────────────┘    └──────────────────────┘               │   │
│  │                      │                        │                             │   │
│  │                      └───────────┬────────────┘                             │   │
│  │                                  │                                          │   │
│  │                    <<interface>> │ EmbeddingProvider                        │   │
│  │                    ──────────────┴──────────────                            │   │
│  │                    + generate_embedding(text)                               │   │
│  │                    + health_check()                                         │   │
│  │                                                                             │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
│                             │                                                       │
│                             ▼                                                       │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │                        OpenSearchService                                     │   │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐   │   │
│  │  │   Index     │ │  Document   │ │   Vector    │ │   Hybrid            │   │   │
│  │  │  Management │ │  CRUD       │ │   Search    │ │   Search            │   │   │
│  │  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Class Diagrams

### 4.1 Embedding Provider Classes

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                          EMBEDDING PROVIDER CLASS DIAGRAM                            │
└─────────────────────────────────────────────────────────────────────────────────────┘

                            ┌─────────────────────────────┐
                            │   <<abstract>>              │
                            │   EmbeddingProvider         │
                            ├─────────────────────────────┤
                            │ + name: str                 │
                            │ + dimensions: int           │
                            │ + model_name: str           │
                            ├─────────────────────────────┤
                            │ + generate_embedding(text)  │
                            │ + generate_embeddings_batch │
                            │ + health_check()            │
                            └──────────────┬──────────────┘
                                           │
                       ┌───────────────────┴───────────────────┐
                       │                                       │
                       ▼                                       ▼
        ┌─────────────────────────────┐         ┌─────────────────────────────┐
        │  GeminiEmbeddingProvider    │         │  OllamaEmbeddingProvider    │
        ├─────────────────────────────┤         ├─────────────────────────────┤
        │ - _genai: genai             │         │ - _base_url: str            │
        │ - _model: str               │         │ - _model: str               │
        │ - _configured: bool         │         │ - _timeout: int             │
        ├─────────────────────────────┤         ├─────────────────────────────┤
        │ + name: "Google Gemini"     │         │ + name: "Ollama (Local)"    │
        │ + dimensions: 768           │         │ + dimensions: varies        │
        │ + generate_embedding()      │         │ + generate_embedding()      │
        │ + health_check()            │         │ + health_check()            │
        └─────────────────────────────┘         └─────────────────────────────┘


        ┌─────────────────────────────────────────────────────────────────────┐
        │                    EmbeddingProviderFactory                          │
        ├─────────────────────────────────────────────────────────────────────┤
        │ - _providers: Dict[str, Type[EmbeddingProvider]]                    │
        ├─────────────────────────────────────────────────────────────────────┤
        │ + get_provider(name: str) -> EmbeddingProvider                      │
        │ + list_providers() -> List[str]                                     │
        │ + register_provider(name, class)                                    │
        │ + check_all_providers() -> Dict                                     │
        └─────────────────────────────────────────────────────────────────────┘
```

### 4.2 Document Processor Class

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                          DOCUMENT PROCESSOR CLASS DIAGRAM                            │
└─────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              DocumentProcessor                                       │
├─────────────────────────────────────────────────────────────────────────────────────┤
│ - settings: Settings                                                                │
│ - _embedding_provider: EmbeddingProvider                                            │
│ + SUPPORTED_EXTENSIONS: List[str] = ['pdf', 'txt', 'json', 'jpg', 'jpeg', 'png']   │
├─────────────────────────────────────────────────────────────────────────────────────┤
│ + __init__()                                                                        │
│ + validate_file(filename, file_size) -> Tuple[bool, str]                           │
│ + extract_text(file_content, filename) -> Dict[str, Any]                           │
│ + extract_text_from_pdf(file_content) -> Dict[str, Any]                            │
│ + extract_text_from_txt(file_content) -> Dict[str, Any]                            │
│ + extract_text_from_json(file_content) -> Dict[str, Any]                           │
│ + extract_text_from_image(file_content, filename) -> Dict[str, Any]                │
│ + chunk_text(text, chunk_size, chunk_overlap) -> List[Dict]                        │
│ + generate_embedding(text) -> List[float]                                          │
│ + generate_embeddings_batch(chunks) -> List[Dict]                                  │
│ + get_processing_stats(text, chunks) -> Dict[str, Any]                             │
│ + get_embedding_info() -> Dict[str, Any]                                           │
│ + embeddings_configured: bool (property)                                           │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                           │
                                           │ uses
                                           ▼
                            ┌─────────────────────────────┐
                            │     EmbeddingProvider       │
                            └─────────────────────────────┘
```

### 4.3 OpenSearch Service Class

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                          OPENSEARCH SERVICE CLASS DIAGRAM                            │
└─────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              OpenSearchService                                       │
├─────────────────────────────────────────────────────────────────────────────────────┤
│ - settings: Settings                                                                │
│ - base_url: str                                                                     │
│ - auth: Tuple[str, str]                                                             │
│ - verify_certs: bool                                                                │
│ + index_name: str                                                                   │
├─────────────────────────────────────────────────────────────────────────────────────┤
│ + __init__()                                                                        │
│ + _get_client() -> httpx.Client                                                     │
│ + test_connection() -> Dict[str, Any]                                               │
│ + create_index(recreate: bool) -> Dict[str, Any]                                   │
│ + delete_index() -> Dict[str, Any]                                                 │
│ + get_index_stats() -> Dict[str, Any]                                              │
│ + index_document(doc: Dict) -> Dict[str, Any]                                      │
│ + delete_document(s3_key: str) -> Dict[str, Any]                                   │
│ + list_indexed_documents() -> List[Dict]                                           │
│ + search(query, k, use_hybrid) -> List[Dict]                                       │
│ + _vector_search(embedding, k) -> List[Dict]                                       │
│ + _hybrid_search(query, embedding, k) -> List[Dict]                                │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### 4.4 Configuration Class

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              SETTINGS CLASS DIAGRAM                                  │
└─────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────┐
│                           Settings (BaseSettings)                                    │
├─────────────────────────────────────────────────────────────────────────────────────┤
│ # AWS S3 Configuration                                                              │
│ + AWS_ACCESS_KEY_ID: str                                                            │
│ + AWS_SECRET_ACCESS_KEY: str                                                        │
│ + AWS_REGION: str = "us-east-1"                                                     │
│ + S3_BUCKET_NAME: str                                                               │
│ + S3_FOLDER_PREFIX: str = "uploads/"                                                │
│                                                                                     │
│ # OpenSearch Configuration                                                          │
│ + OPENSEARCH_HOST: str = "localhost"                                                │
│ + OPENSEARCH_PORT: int = 9200                                                       │
│ + OPENSEARCH_USERNAME: str = "admin"                                                │
│ + OPENSEARCH_PASSWORD: str = "admin"                                                │
│ + OPENSEARCH_USE_SSL: bool = True                                                   │
│ + OPENSEARCH_VERIFY_CERTS: bool = False                                             │
│ + OPENSEARCH_INDEX_NAME: str = "whatsapp_knowledge_base"                            │
│                                                                                     │
│ # Embedding Configuration                                                           │
│ + EMBEDDING_PROVIDER: str = "gemini"                                                │
│ + GOOGLE_API_KEY: str                                                               │
│ + GEMINI_EMBEDDING_MODEL: str = "models/text-embedding-004"                         │
│ + OLLAMA_BASE_URL: str = "http://localhost:11434"                                   │
│ + OLLAMA_EMBEDDING_MODEL: str = "nomic-embed-text"                                  │
│ + OLLAMA_TIMEOUT: int = 60                                                          │
│                                                                                     │
│ # Authentication                                                                    │
│ + AUTH_USERNAME: str = "admin"                                                      │
│ + AUTH_PASSWORD: str = "admin123"                                                   │
│ + SECRET_KEY: str                                                                   │
│ + SESSION_EXPIRE_HOURS: int = 24                                                    │
├─────────────────────────────────────────────────────────────────────────────────────┤
│ class Config:                                                                       │
│     env_file = ".env"                                                               │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Data Models

### 5.1 OpenSearch Document Schema

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                          OPENSEARCH DOCUMENT SCHEMA                                  │
└─────────────────────────────────────────────────────────────────────────────────────┘

Index: whatsapp_knowledge_base

┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              Document Structure                                      │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│  {                                                                                  │
│    "content": string,              // Chunk text content                            │
│    "content_embedding": float[768], // Vector embedding                             │
│    "filename": string,             // Original filename                             │
│    "s3_key": string,               // Unique document identifier                    │
│    "file_type": string,            // pdf, txt, json, jpg, etc.                     │
│    "chunk_index": integer,         // Chunk position in document                    │
│    "total_chunks": integer,        // Total chunks in document                      │
│    "indexed_at": datetime,         // ISO timestamp                                 │
│    "metadata": {                   // Additional metadata                           │
│      "chars": integer,             // Character count                               │
│      "onboarding_method": string,  // "direct_upload" | "full_auto"                 │
│      "embedding_provider": string, // "Google Gemini" | "Ollama"                    │
│      "embedding_model": string     // Model used for embedding                      │
│    }                                                                                │
│  }                                                                                  │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘

Index Mapping:
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  content_embedding:                                                                 │
│    type: knn_vector                                                                 │
│    dimension: 768                                                                   │
│    method:                                                                          │
│      name: hnsw                                                                     │
│      space_type: cosinesimil                                                        │
│      engine: lucene                                                                 │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Chunk Data Structure

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              CHUNK DATA STRUCTURE                                    │
└─────────────────────────────────────────────────────────────────────────────────────┘

Processing Pipeline:

  Raw Chunk                    Embedded Chunk                  Indexed Chunk
  ──────────                   ──────────────                  ─────────────
  {                            {                               {
    "index": 0,       ──>        "index": 0,          ──>       "content": "...",
    "text": "...",               "text": "...",                 "content_embedding": [...],
    "chars": 985,                "chars": 985,                  "filename": "doc.pdf",
    "start": 0,                  "start": 0,                    "chunk_index": 0,
    "end": 985                   "end": 985,                    "total_chunks": 10,
  }                              "embedding": [0.1, ...],       "indexed_at": "2024-...",
                                 "embedding_status": "success", "metadata": {...}
                                 "embedding_provider": "..."  }
                               }
```

---

## 6. Sequence Diagrams

### 6.1 Document Onboarding Flow

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                          DOCUMENT ONBOARDING SEQUENCE                                │
└─────────────────────────────────────────────────────────────────────────────────────┘

┌──────┐     ┌──────────┐     ┌─────────────┐     ┌──────────────┐     ┌──────────┐
│Client│     │  Router  │     │  Document   │     │  Embedding   │     │OpenSearch│
│      │     │          │     │  Processor  │     │  Provider    │     │          │
└──┬───┘     └────┬─────┘     └──────┬──────┘     └──────┬───────┘     └────┬─────┘
   │              │                  │                   │                  │
   │ Step 1: Upload                  │                   │                  │
   │──────────────>                  │                   │                  │
   │              │ validate_file()  │                   │                  │
   │              │─────────────────>│                   │                  │
   │              │<─────────────────│                   │                  │
   │<─────────────│ {success, content_b64}              │                  │
   │              │                  │                   │                  │
   │ Step 2: Extract                 │                   │                  │
   │──────────────>                  │                   │                  │
   │              │ extract_text()   │                   │                  │
   │              │─────────────────>│                   │                  │
   │              │<─────────────────│ (PyMuPDF/decode)  │                  │
   │<─────────────│ {text, pages, chars}                │                  │
   │              │                  │                   │                  │
   │ Step 3: Chunk                   │                   │                  │
   │──────────────>                  │                   │                  │
   │              │ chunk_text()     │                   │                  │
   │              │─────────────────>│                   │                  │
   │              │<─────────────────│                   │                  │
   │<─────────────│ {chunks[], stats}│                   │                  │
   │              │                  │                   │                  │
   │ Step 4: Embed                   │                   │                  │
   │──────────────>                  │                   │                  │
   │              │ generate_embeddings_batch()          │                  │
   │              │─────────────────>│                   │                  │
   │              │                  │ generate_embedding()                 │
   │              │                  │──────────────────>│                  │
   │              │                  │<──────────────────│ [768 floats]     │
   │              │                  │   (per chunk)     │                  │
   │              │<─────────────────│                   │                  │
   │<─────────────│ {embedded_chunks[]}                  │                  │
   │              │                  │                   │                  │
   │ Step 5: Index                   │                   │                  │
   │──────────────>                  │                   │                  │
   │              │                  │                   │  POST /_doc      │
   │              │────────────────────────────────────────────────────────>│
   │              │<────────────────────────────────────────────────────────│
   │<─────────────│ {indexed_chunks, doc_ids}            │                  │
   │              │                  │                   │                  │
```

### 6.2 Search Flow

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              SEARCH SEQUENCE                                         │
└─────────────────────────────────────────────────────────────────────────────────────┘

┌──────┐     ┌──────────┐     ┌──────────────┐     ┌──────────┐
│Client│     │  Router  │     │  Embedding   │     │OpenSearch│
│      │     │          │     │  Provider    │     │          │
└──┬───┘     └────┬─────┘     └──────┬───────┘     └────┬─────┘
   │              │                  │                  │
   │ GET /search?query=...          │                  │
   │──────────────>                  │                  │
   │              │                  │                  │
   │              │ generate_embedding(query)           │
   │              │─────────────────>│                  │
   │              │<─────────────────│ [768 floats]     │
   │              │                  │                  │
   │              │ Hybrid Search (vector + text)       │
   │              │────────────────────────────────────>│
   │              │                  │                  │
   │              │                  │   KNN + Match    │
   │              │<────────────────────────────────────│
   │              │                  │   {results[]}    │
   │              │                  │                  │
   │<─────────────│ {results, scores}│                  │
   │              │                  │                  │
```

---

## 7. Technology Stack

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              TECHNOLOGY STACK                                        │
└─────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                  FRONTEND                                            │
├─────────────────────────────────────────────────────────────────────────────────────┤
│  • HTML5 / CSS3 / JavaScript (Vanilla)                                              │
│  • Jinja2 Templates                                                                 │
│  • Responsive Design (Mobile-first)                                                 │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                  BACKEND                                             │
├─────────────────────────────────────────────────────────────────────────────────────┤
│  • Python 3.9+                                                                      │
│  • FastAPI (Web Framework)                                                          │
│  • Pydantic (Data Validation)                                                       │
│  • HTTPX (HTTP Client)                                                              │
│  • PyMuPDF (PDF Processing)                                                         │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              AI / ML SERVICES                                        │
├─────────────────────────────────────────────────────────────────────────────────────┤
│  • Google Gemini API (Cloud Embeddings + Vision OCR)                                │
│  • Ollama (Local Embeddings)                                                        │
│    - nomic-embed-text (768d)                                                        │
│    - mxbai-embed-large (1024d)                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                 DATA STORES                                          │
├─────────────────────────────────────────────────────────────────────────────────────┤
│  • OpenSearch 2.x (Vector Database)                                                 │
│    - KNN Plugin (HNSW algorithm)                                                    │
│    - Cosine Similarity                                                              │
│  • SQLite (File Metadata - optional)                                                │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                               INFRASTRUCTURE                                         │
├─────────────────────────────────────────────────────────────────────────────────────┤
│  • Docker (Containerization)                                                        │
│  • Uvicorn (ASGI Server)                                                            │
│  • Environment Variables (.env)                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Dependency Graph

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              DEPENDENCY GRAPH                                        │
└─────────────────────────────────────────────────────────────────────────────────────┘

                                 ┌─────────┐
                                 │  main   │
                                 │  .py    │
                                 └────┬────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    │                 │                 │
                    ▼                 ▼                 ▼
             ┌──────────┐      ┌──────────┐      ┌──────────┐
             │  auth    │      │  files   │      │knowledge │
             │  router  │      │  router  │      │base router
             └──────────┘      └────┬─────┘      └────┬─────┘
                                    │                 │
                                    │      ┌──────────┴──────────┐
                                    │      │                     │
                                    ▼      ▼                     ▼
                             ┌──────────────────┐    ┌───────────────────┐
                             │    document      │    │    opensearch     │
                             │    processor     │    │    service        │
                             └────────┬─────────┘    └───────────────────┘
                                      │
                                      ▼
                             ┌──────────────────┐
                             │    embedding     │
                             │    providers     │
                             └────────┬─────────┘
                                      │
                         ┌────────────┴────────────┐
                         │                         │
                         ▼                         ▼
                  ┌─────────────┐          ┌─────────────┐
                  │   Gemini    │          │   Ollama    │
                  │  Provider   │          │  Provider   │
                  └─────────────┘          └─────────────┘
```

---

*Last Updated: November 2024*
