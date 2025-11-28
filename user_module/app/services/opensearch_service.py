"""
OpenSearch Service for WhatsApp Bot Knowledge Base Management
Uses HTTP REST API instead of opensearch-py library

This service handles:
- Connecting to OpenSearch via REST API
- Creating/managing the knowledge base index
- Indexing documents with embeddings
- Searching documents for the WhatsApp bot
"""

import warnings
from typing import Optional, List, Dict, Any
from datetime import datetime
import json
import httpx
import ssl

from ..config import get_settings
from .embedding_providers import get_embedding_provider

# Suppress SSL warnings for self-signed certs
warnings.filterwarnings("ignore", message=".*Unverified HTTPS request.*")


class OpenSearchService:
    """Service for managing OpenSearch knowledge base for WhatsApp bot via REST API"""

    def __init__(self):
        self.settings = get_settings()
        self._embeddings_configured = False
        self._embedding_provider = None

        # Build base URL
        protocol = "https" if self.settings.OPENSEARCH_USE_SSL else "http"
        self.base_url = f"{protocol}://{self.settings.OPENSEARCH_HOST}:{self.settings.OPENSEARCH_PORT}"

        # Auth credentials
        self.auth = (self.settings.OPENSEARCH_USERNAME, self.settings.OPENSEARCH_PASSWORD)

        # Initialize embedding provider (supports Gemini and Ollama)
        try:
            self._embedding_provider = get_embedding_provider()
            self._embeddings_configured = self._embedding_provider.health_check()
        except Exception as e:
            print(f"Warning: Failed to initialize embedding provider: {e}")
            self._embeddings_configured = False

    def _get_client(self) -> httpx.Client:
        """Create HTTP client with appropriate SSL settings"""
        verify = self.settings.OPENSEARCH_VERIFY_CERTS
        return httpx.Client(
            base_url=self.base_url,
            auth=self.auth,
            verify=verify,
            timeout=30.0
        )

    @property
    def index_name(self) -> str:
        return self.settings.OPENSEARCH_INDEX_NAME

    def test_connection(self) -> Dict[str, Any]:
        """Test connection to OpenSearch"""
        try:
            with self._get_client() as client:
                response = client.get("/")
                response.raise_for_status()
                info = response.json()
                return {
                    "connected": True,
                    "cluster_name": info.get("cluster_name", "unknown"),
                    "version": info.get("version", {}).get("number", "unknown")
                }
        except Exception as e:
            return {
                "connected": False,
                "error": str(e)
            }

    def create_index(self, recreate: bool = False) -> Dict[str, Any]:
        """Create the knowledge base index with appropriate mappings"""
        try:
            with self._get_client() as client:
                # Check if index exists
                response = client.head(f"/{self.index_name}")
                index_exists = response.status_code == 200

                if index_exists:
                    if recreate:
                        client.delete(f"/{self.index_name}")
                    else:
                        return {
                            "success": True,
                            "message": f"Index '{self.index_name}' already exists",
                            "created": False
                        }

                # Define index mapping with vector field for embeddings
                index_body = {
                    "settings": {
                        "index": {
                            "number_of_shards": 1,
                            "number_of_replicas": 0,
                            "knn": True
                        }
                    },
                    "mappings": {
                        "properties": {
                            "content": {
                                "type": "text",
                                "analyzer": "standard"
                            },
                            "content_embedding": {
                                "type": "knn_vector",
                                "dimension": 768,
                                "method": {
                                    "name": "hnsw",
                                    "space_type": "cosinesimil",
                                    "engine": "lucene",
                                    "parameters": {
                                        "ef_construction": 128,
                                        "m": 16
                                    }
                                }
                            },
                            "filename": {
                                "type": "keyword"
                            },
                            "s3_key": {
                                "type": "keyword"
                            },
                            "file_type": {
                                "type": "keyword"
                            },
                            "chunk_index": {
                                "type": "integer"
                            },
                            "total_chunks": {
                                "type": "integer"
                            },
                            "indexed_at": {
                                "type": "date"
                            },
                            "metadata": {
                                "type": "object",
                                "enabled": True
                            }
                        }
                    }
                }

                response = client.put(
                    f"/{self.index_name}",
                    json=index_body
                )
                response.raise_for_status()

                return {
                    "success": True,
                    "message": f"Index '{self.index_name}' created successfully",
                    "created": True
                }
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to create index: {str(e)}",
                "created": False
            }

    def get_embedding(self, text: str) -> List[float]:
        """Generate embedding for text using configured provider (Gemini or Ollama)"""
        if not self._embeddings_configured or not self._embedding_provider:
            raise ValueError("Embedding provider not configured or not available")

        try:
            return self._embedding_provider.generate_embedding(text)
        except Exception as e:
            raise ValueError(f"Failed to generate embedding: {str(e)}")

    def chunk_text(self, text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
        """Split text into overlapping chunks for indexing"""
        if len(text) <= chunk_size:
            return [text]

        chunks = []
        start = 0

        while start < len(text):
            end = start + chunk_size

            # Try to break at a sentence or paragraph boundary
            if end < len(text):
                # Look for paragraph break
                para_break = text.rfind('\n\n', start, end)
                if para_break > start + chunk_size // 2:
                    end = para_break + 2
                else:
                    # Look for sentence break
                    for punct in ['. ', '.\n', '? ', '!\n']:
                        sent_break = text.rfind(punct, start, end)
                        if sent_break > start + chunk_size // 2:
                            end = sent_break + len(punct)
                            break

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            start = end - overlap
            if start >= len(text):
                break

        return chunks

    def index_document(
        self,
        content: str,
        filename: str,
        s3_key: str,
        file_type: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Index a document into OpenSearch with chunking and embeddings"""

        # Ensure index exists
        self.create_index(recreate=False)

        # Chunk the content
        chunks = self.chunk_text(content)
        total_chunks = len(chunks)

        indexed_count = 0
        errors = []
        doc_ids = []

        try:
            with self._get_client() as client:
                for i, chunk in enumerate(chunks):
                    try:
                        # Generate embedding
                        embedding = self.get_embedding(chunk)

                        # Create document
                        doc = {
                            "content": chunk,
                            "content_embedding": embedding,
                            "filename": filename,
                            "s3_key": s3_key,
                            "file_type": file_type,
                            "chunk_index": i,
                            "total_chunks": total_chunks,
                            "indexed_at": datetime.utcnow().isoformat(),
                            "metadata": metadata or {}
                        }

                        # Index document
                        response = client.post(
                            f"/{self.index_name}/_doc?refresh=true",
                            json=doc
                        )
                        response.raise_for_status()
                        result = response.json()

                        doc_ids.append(result["_id"])
                        indexed_count += 1

                    except Exception as e:
                        errors.append(f"Chunk {i}: {str(e)}")

        except Exception as e:
            errors.append(f"Connection error: {str(e)}")

        return {
            "success": indexed_count > 0,
            "indexed_chunks": indexed_count,
            "total_chunks": total_chunks,
            "doc_ids": doc_ids,
            "errors": errors if errors else None
        }

    def search(
        self,
        query: str,
        k: int = 5,
        use_hybrid: bool = True
    ) -> List[Dict[str, Any]]:
        """Search the knowledge base using semantic search"""

        results = []

        try:
            with self._get_client() as client:
                if use_hybrid and self._embeddings_configured:
                    # Hybrid search: combine vector and text search
                    query_embedding = self.get_embedding(query)

                    search_body = {
                        "size": k,
                        "query": {
                            "bool": {
                                "should": [
                                    {
                                        "knn": {
                                            "content_embedding": {
                                                "vector": query_embedding,
                                                "k": k
                                            }
                                        }
                                    },
                                    {
                                        "match": {
                                            "content": {
                                                "query": query,
                                                "boost": 0.3
                                            }
                                        }
                                    }
                                ]
                            }
                        }
                    }
                else:
                    # Text-only search
                    search_body = {
                        "size": k,
                        "query": {
                            "match": {
                                "content": query
                            }
                        }
                    }

                response = client.post(
                    f"/{self.index_name}/_search",
                    json=search_body
                )
                response.raise_for_status()
                data = response.json()

                for hit in data["hits"]["hits"]:
                    results.append({
                        "content": hit["_source"]["content"],
                        "filename": hit["_source"]["filename"],
                        "s3_key": hit["_source"]["s3_key"],
                        "score": hit["_score"],
                        "chunk_index": hit["_source"].get("chunk_index", 0),
                        "metadata": hit["_source"].get("metadata", {})
                    })

        except Exception as e:
            raise ValueError(f"Search failed: {str(e)}")

        return results

    def delete_document(self, s3_key: str) -> Dict[str, Any]:
        """Delete all chunks of a document by s3_key"""
        try:
            with self._get_client() as client:
                response = client.post(
                    f"/{self.index_name}/_delete_by_query?refresh=true",
                    json={
                        "query": {
                            "term": {
                                "s3_key": s3_key
                            }
                        }
                    }
                )
                response.raise_for_status()
                result = response.json()

                return {
                    "success": True,
                    "deleted": result.get("deleted", 0)
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def get_index_stats(self) -> Dict[str, Any]:
        """Get statistics about the knowledge base index"""
        try:
            with self._get_client() as client:
                # Check if index exists
                response = client.head(f"/{self.index_name}")
                if response.status_code != 200:
                    return {
                        "exists": False,
                        "message": f"Index '{self.index_name}' does not exist"
                    }

                # Get index stats
                response = client.get(f"/{self.index_name}/_stats")
                response.raise_for_status()
                stats = response.json()
                index_stats = stats["indices"][self.index_name]

                # Get unique document count
                response = client.post(
                    f"/{self.index_name}/_search",
                    json={
                        "size": 0,
                        "aggs": {
                            "unique_files": {
                                "cardinality": {
                                    "field": "s3_key"
                                }
                            }
                        }
                    }
                )
                response.raise_for_status()
                unique_docs = response.json()

                return {
                    "exists": True,
                    "total_chunks": index_stats["primaries"]["docs"]["count"],
                    "unique_documents": unique_docs["aggregations"]["unique_files"]["value"],
                    "size_bytes": index_stats["primaries"]["store"]["size_in_bytes"],
                    "size_mb": round(index_stats["primaries"]["store"]["size_in_bytes"] / (1024 * 1024), 2)
                }
        except Exception as e:
            return {
                "exists": False,
                "error": str(e)
            }

    def list_indexed_documents(self) -> List[Dict[str, Any]]:
        """List all unique documents in the index"""
        try:
            with self._get_client() as client:
                response = client.post(
                    f"/{self.index_name}/_search",
                    json={
                        "size": 0,
                        "aggs": {
                            "documents": {
                                "terms": {
                                    "field": "s3_key",
                                    "size": 1000
                                },
                                "aggs": {
                                    "doc_info": {
                                        "top_hits": {
                                            "size": 1,
                                            "_source": ["filename", "file_type", "total_chunks", "indexed_at"]
                                        }
                                    }
                                }
                            }
                        }
                    }
                )
                response.raise_for_status()
                data = response.json()

                documents = []
                for bucket in data["aggregations"]["documents"]["buckets"]:
                    hit = bucket["doc_info"]["hits"]["hits"][0]["_source"]
                    documents.append({
                        "s3_key": bucket["key"],
                        "filename": hit.get("filename", "unknown"),
                        "file_type": hit.get("file_type", "unknown"),
                        "total_chunks": hit.get("total_chunks", 1),
                        "indexed_at": hit.get("indexed_at"),
                        "chunk_count": bucket["doc_count"]
                    })

                return documents
        except Exception as e:
            return []

    def delete_index(self) -> Dict[str, Any]:
        """Delete the entire index"""
        try:
            with self._get_client() as client:
                # Check if index exists
                response = client.head(f"/{self.index_name}")
                if response.status_code != 200:
                    return {
                        "success": True,
                        "message": f"Index '{self.index_name}' does not exist"
                    }

                response = client.delete(f"/{self.index_name}")
                response.raise_for_status()

                return {
                    "success": True,
                    "message": f"Index '{self.index_name}' deleted successfully"
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }


# Singleton instance
_opensearch_service: Optional[OpenSearchService] = None


def get_opensearch_service() -> OpenSearchService:
    global _opensearch_service
    if _opensearch_service is None:
        _opensearch_service = OpenSearchService()
    return _opensearch_service
