# User Module - Developer Guide

A comprehensive guide for setting up and using the WhatsApp Knowledge Base Admin Portal.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Quick Start](#quick-start)
3. [Configuration](#configuration)
4. [Embedding Providers](#embedding-providers)
5. [Document Onboarding Flow](#document-onboarding-flow)
6. [API Reference](#api-reference)
7. [Troubleshooting](#troubleshooting)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           USER MODULE (Admin Portal)                         │
│                                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │   Upload    │───>│   Extract   │───>│    Chunk    │───>│   Embed     │  │
│  │   & Valid   │    │    Text     │    │    Text     │    │   Vectors   │  │
│  └─────────────┘    └─────────────┘    └─────────────┘    └──────┬──────┘  │
│                                                                   │         │
│                                                                   ▼         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         OpenSearch Index                             │   │
│  │                    (whatsapp_knowledge_base)                        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      │ Vector Search
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         WHATSAPP-MAIN (Chat Service)                         │
│                                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │   Twilio    │───>│   Query     │───>│   Gemini    │───>│   Twilio    │  │
│  │   Webhook   │    │   Search    │    │    LLM      │    │   Response  │  │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility |
|-----------|----------------|
| **User Module** | Document onboarding, KB management (this repo) |
| **WhatsApp-main** | Chat interface, Twilio integration, LLM responses |
| **OpenSearch** | Vector storage and similarity search |

---

## Quick Start

### Prerequisites

- Python 3.9+
- OpenSearch running at `https://localhost:9200`
- One of: Google API Key (Gemini) OR Ollama installed locally

### Installation

```bash
# 1. Navigate to user_module
cd user_module

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create .env file (copy from example)
cp .env.example .env

# 5. Edit .env with your settings
nano .env  # or use your preferred editor

# 6. Run the application
python -m uvicorn app.main:app --reload --port 8000
```

### Access

- **URL**: http://localhost:8000
- **Login**: `admin` / `admin123`

---

## Configuration

### Environment Variables (.env)

```env
# ============================================
# REQUIRED: OpenSearch Configuration
# ============================================
OPENSEARCH_HOST=localhost
OPENSEARCH_PORT=9200
OPENSEARCH_USERNAME=admin
OPENSEARCH_PASSWORD=admin
OPENSEARCH_USE_SSL=true
OPENSEARCH_VERIFY_CERTS=false
OPENSEARCH_INDEX_NAME=whatsapp_knowledge_base

# ============================================
# REQUIRED: Embedding Provider
# ============================================
# Options: "gemini" or "ollama"
EMBEDDING_PROVIDER=gemini

# ============================================
# For Gemini (Cloud)
# ============================================
GOOGLE_API_KEY=your_google_api_key_here
GEMINI_EMBEDDING_MODEL=models/text-embedding-004

# ============================================
# For Ollama (Local)
# ============================================
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_EMBEDDING_MODEL=nomic-embed-text
OLLAMA_TIMEOUT=60

# ============================================
# OPTIONAL: Additional Settings
# ============================================
# For image OCR (requires Google API key)
# GOOGLE_API_KEY is also used for image text extraction

# File size limit
MAX_FILE_SIZE_MB=50

# Authentication
AUTH_USERNAME=admin
AUTH_PASSWORD=admin123
```

---

## Embedding Providers

### Provider Comparison

```
┌────────────────────────────────────────────────────────────────────────────┐
│                        EMBEDDING PROVIDERS                                  │
├──────────────────────────────┬─────────────────────────────────────────────┤
│         GEMINI (Cloud)       │              OLLAMA (Local)                 │
├──────────────────────────────┼─────────────────────────────────────────────┤
│  ✓ No local setup            │  ✓ Free, no API costs                       │
│  ✓ Fast, reliable            │  ✓ Data stays local                         │
│  ✓ 768 dimensions            │  ✓ Works offline                            │
│  ✗ Requires API key          │  ✗ Requires local GPU/CPU                   │
│  ✗ API costs                 │  ✗ Slower on CPU-only                       │
├──────────────────────────────┼─────────────────────────────────────────────┤
│  Model: text-embedding-004   │  Models: nomic-embed-text (768d)            │
│  Dimensions: 768             │          mxbai-embed-large (1024d)          │
└──────────────────────────────┴─────────────────────────────────────────────┘
```

### Using Gemini (Cloud)

```env
# .env
EMBEDDING_PROVIDER=gemini
GOOGLE_API_KEY=AIzaSy...your_key_here
GEMINI_EMBEDDING_MODEL=models/text-embedding-004
```

**Get API Key**: https://makersuite.google.com/app/apikey

### Using Ollama (Local)

```bash
# 1. Install Ollama
# macOS
brew install ollama

# Linux
curl -fsSL https://ollama.com/install.sh | sh

# 2. Start Ollama server
ollama serve

# 3. Pull embedding model
ollama pull nomic-embed-text

# 4. Configure .env
EMBEDDING_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_EMBEDDING_MODEL=nomic-embed-text
```

### Available Ollama Embedding Models

| Model | Dimensions | Size | Notes |
|-------|------------|------|-------|
| `nomic-embed-text` | 768 | 274MB | Recommended, same dims as Gemini |
| `mxbai-embed-large` | 1024 | 670MB | Higher quality, larger vectors |
| `all-minilm` | 384 | 45MB | Smallest, fastest |
| `snowflake-arctic-embed` | 1024 | 670MB | Good for retrieval |

### Provider Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    EmbeddingProviderFactory                      │
│                                                                 │
│   EMBEDDING_PROVIDER=gemini        EMBEDDING_PROVIDER=ollama    │
│            │                                │                   │
│            ▼                                ▼                   │
│   ┌─────────────────┐              ┌─────────────────┐         │
│   │ GeminiEmbedding │              │ OllamaEmbedding │         │
│   │    Provider     │              │    Provider     │         │
│   ├─────────────────┤              ├─────────────────┤         │
│   │ • Cloud API     │              │ • Local HTTP    │         │
│   │ • 768 dims      │              │ • Configurable  │         │
│   │ • Fast          │              │ • Free          │         │
│   └────────┬────────┘              └────────┬────────┘         │
│            │                                │                   │
│            └────────────┬───────────────────┘                   │
│                         │                                       │
│                         ▼                                       │
│              generate_embedding(text)                           │
│                         │                                       │
│                         ▼                                       │
│                  List[float] (768d)                             │
└─────────────────────────────────────────────────────────────────┘
```

---

## Document Onboarding Flow

### Step-by-Step Process

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        DOCUMENT ONBOARDING PIPELINE                          │
└─────────────────────────────────────────────────────────────────────────────┘

     STEP 1              STEP 2              STEP 3              STEP 4              STEP 5
  ┌─────────┐        ┌─────────┐        ┌─────────┐        ┌─────────┐        ┌─────────┐
  │ UPLOAD  │───────>│ EXTRACT │───────>│  CHUNK  │───────>│  EMBED  │───────>│  INDEX  │
  │         │        │         │        │         │        │         │        │         │
  │  .pdf   │        │ PyMuPDF │        │ 1000    │        │ Gemini/ │        │OpenSearch│
  │  .txt   │        │  Text   │        │ chars   │        │ Ollama  │        │  Store  │
  │  .json  │        │  JSON   │        │ overlap │        │         │        │         │
  │  .jpg   │        │  OCR    │        │  200    │        │ 768 dim │        │  Done!  │
  └─────────┘        └─────────┘        └─────────┘        └─────────┘        └─────────┘
       │                  │                  │                  │                  │
       ▼                  ▼                  ▼                  ▼                  ▼
  ┌─────────┐        ┌─────────┐        ┌─────────┐        ┌─────────┐        ┌─────────┐
  │Validate │        │Raw Text │        │ Chunks  │        │Embedded │        │Searchable│
  │  File   │        │  +Stats │        │  Array  │        │ Chunks  │        │   KB    │
  └─────────┘        └─────────┘        └─────────┘        └─────────┘        └─────────┘
```

### Supported File Types

| Type | Extension | Extraction Method |
|------|-----------|-------------------|
| PDF | `.pdf` | PyMuPDF (fitz) |
| Text | `.txt` | Direct decode (UTF-8/Latin-1) |
| JSON | `.json` | JSON parse → structured text |
| Images | `.jpg`, `.jpeg`, `.png` | Gemini Vision OCR |

### Chunking Configuration

```
┌─────────────────────────────────────────────────────────────────┐
│                    TEXT CHUNKING                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Original Text (5000 chars)                                     │
│  ════════════════════════════════════════════════════════════   │
│                                                                 │
│  chunk_size = 1000                                              │
│  chunk_overlap = 200                                            │
│                                                                 │
│  ┌──────────────┐                                               │
│  │   Chunk 1    │ (0-1000)                                      │
│  └──────┬───────┘                                               │
│         │ overlap                                                │
│  ┌──────┴───────┐                                               │
│  │   Chunk 2    │ (800-1800)                                    │
│  └──────┬───────┘                                               │
│         │ overlap                                                │
│  ┌──────┴───────┐                                               │
│  │   Chunk 3    │ (1600-2600)                                   │
│  └──────┬───────┘                                               │
│         │                                                        │
│        ...                                                       │
│                                                                 │
│  Smart boundaries: Splits at ¶ > \n > . > , > space             │
└─────────────────────────────────────────────────────────────────┘
```

---

## API Reference

### Base URL
```
http://localhost:8000/api/knowledge-base
```

### Endpoints Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           API ENDPOINTS                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ONBOARDING (Step-wise)                                                     │
│  ──────────────────────                                                     │
│  POST /onboard/step1-upload     Upload & validate file                      │
│  POST /onboard/step2-extract    Extract text from file                      │
│  POST /onboard/step3-chunk      Split text into chunks                      │
│  POST /onboard/step4-embed      Generate embeddings                         │
│  POST /onboard/step5-index      Index to OpenSearch                         │
│  POST /onboard/full             One-click full onboarding                   │
│                                                                             │
│  STATUS & MANAGEMENT                                                        │
│  ───────────────────                                                        │
│  GET  /status                   OpenSearch + embedding status               │
│  GET  /embedding/status         Detailed embedding provider info            │
│  POST /index/create             Create OpenSearch index                     │
│  DELETE /index                  Delete entire index                         │
│                                                                             │
│  DOCUMENTS                                                                  │
│  ─────────                                                                  │
│  GET  /documents                List indexed documents                      │
│  DELETE /documents/{s3_key}     Remove document from KB                     │
│                                                                             │
│  SEARCH                                                                     │
│  ──────                                                                     │
│  GET  /search?query=...&k=5     Search knowledge base                       │
│  POST /search                   Search (POST method)                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Example: Check System Status

```bash
curl http://localhost:8000/api/knowledge-base/status
```

Response:
```json
{
  "connected": true,
  "cluster_name": "opensearch",
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
    "provider": "Ollama (Local)",
    "model": "nomic-embed-text",
    "dimensions": 768
  }
}
```

### Example: Full Onboarding

```bash
curl -X POST http://localhost:8000/api/knowledge-base/onboard/full \
  -F "file=@document.pdf" \
  -F "chunk_size=1000" \
  -F "chunk_overlap=200"
```

### Example: Search

```bash
curl "http://localhost:8000/api/knowledge-base/search?query=product%20price&k=5"
```

---

## Troubleshooting

### Common Issues

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         TROUBLESHOOTING GUIDE                                │
└─────────────────────────────────────────────────────────────────────────────┘

❌ "Embedding provider not configured"
   ┌────────────────────────────────────────────────────────────────────────┐
   │ Check .env file:                                                       │
   │   • EMBEDDING_PROVIDER is set to "gemini" or "ollama"                 │
   │   • For Gemini: GOOGLE_API_KEY is set                                  │
   │   • For Ollama: Ollama server is running                               │
   └────────────────────────────────────────────────────────────────────────┘

❌ "Cannot connect to Ollama"
   ┌────────────────────────────────────────────────────────────────────────┐
   │ Solutions:                                                             │
   │   1. Start Ollama: ollama serve                                        │
   │   2. Check URL in .env: OLLAMA_BASE_URL=http://localhost:11434         │
   │   3. Verify model exists: ollama list                                  │
   └────────────────────────────────────────────────────────────────────────┘

❌ "Model not found" (Ollama)
   ┌────────────────────────────────────────────────────────────────────────┐
   │ Pull the model first:                                                  │
   │   ollama pull nomic-embed-text                                         │
   │                                                                        │
   │ Or use a different model in .env:                                      │
   │   OLLAMA_EMBEDDING_MODEL=mxbai-embed-large                             │
   └────────────────────────────────────────────────────────────────────────┘

❌ "OpenSearch connection failed"
   ┌────────────────────────────────────────────────────────────────────────┐
   │ Solutions:                                                             │
   │   1. Verify OpenSearch is running on port 9200                         │
   │   2. Check credentials in .env                                         │
   │   3. For SSL issues: OPENSEARCH_VERIFY_CERTS=false                     │
   └────────────────────────────────────────────────────────────────────────┘

❌ "Image OCR failed"
   ┌────────────────────────────────────────────────────────────────────────┐
   │ Image OCR always requires Google API key (uses Gemini Vision)          │
   │   • Set GOOGLE_API_KEY even if using Ollama for embeddings             │
   └────────────────────────────────────────────────────────────────────────┘
```

### Verify Setup

```bash
# 1. Check embedding provider status
curl http://localhost:8000/api/knowledge-base/embedding/status

# 2. Check OpenSearch connection
curl http://localhost:8000/api/knowledge-base/status

# 3. Check Ollama (if using)
curl http://localhost:11434/api/tags

# 4. List available Ollama models
ollama list
```

### Logs

```bash
# Run with debug logging
python -m uvicorn app.main:app --reload --port 8000 --log-level debug
```

---

## Project Structure

```
user_module/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app entry point
│   ├── config.py               # Settings & environment config
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── auth.py             # Authentication routes
│   │   ├── files.py            # File management routes
│   │   └── knowledge_base.py   # KB onboarding routes
│   ├── services/
│   │   ├── __init__.py
│   │   ├── document_processor.py    # Text extraction & chunking
│   │   ├── embedding_providers.py   # Gemini/Ollama providers
│   │   └── opensearch_service.py    # OpenSearch client
│   └── static/
│       ├── css/styles.css
│       └── js/app.js
├── templates/
│   └── index.html              # Main UI template
├── .env.example                # Environment template
├── requirements.txt            # Python dependencies
└── DEVELOPER_GUIDE.md          # This file
```

---

## Adding Custom Embedding Providers

To add a new provider (e.g., OpenAI):

```python
# app/services/embedding_providers.py

class OpenAIEmbeddingProvider(EmbeddingProvider):
    """OpenAI embedding provider"""

    def __init__(self):
        self.settings = get_settings()
        self._client = OpenAI(api_key=self.settings.OPENAI_API_KEY)

    @property
    def name(self) -> str:
        return "OpenAI"

    @property
    def dimensions(self) -> int:
        return 1536  # text-embedding-ada-002

    @property
    def model_name(self) -> str:
        return "text-embedding-ada-002"

    def generate_embedding(self, text: str) -> List[float]:
        response = self._client.embeddings.create(
            model=self.model_name,
            input=text
        )
        return response.data[0].embedding

    def health_check(self) -> Dict[str, Any]:
        # Implementation...

# Register the provider
EmbeddingProviderFactory.register_provider("openai", OpenAIEmbeddingProvider)
```

Then in `.env`:
```env
EMBEDDING_PROVIDER=openai
OPENAI_API_KEY=sk-...
```

---

## Need Help?

- Check the [Troubleshooting](#troubleshooting) section
- Review API responses for error details
- Enable debug logging for more information
