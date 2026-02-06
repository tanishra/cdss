"""
Embeddings Service - Vector embeddings and similarity search using ChromaDB
"""
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
import os

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class EmbeddingsServiceError(Exception):
    """Embeddings service exception."""
    pass


class EmbeddingsService:
    """
    Service for creating embeddings and vector similarity search.
    Uses ChromaDB for vector storage and sentence-transformers for embeddings.
    """
    
    def __init__(self):
        """Initialize embeddings service."""
        self.model = None
        self.chroma_client = None
        self.collection = None
        self._initialize()
    
    def _initialize(self):
        """Initialize embedding model and ChromaDB."""
        try:
            # Initialize sentence transformer model
            logger.info("embeddings_model_loading", model=settings.EMBEDDINGS_MODEL)
            self.model = SentenceTransformer(settings.EMBEDDINGS_MODEL)
            logger.info("embeddings_model_loaded")
            
            # Initialize ChromaDB
            os.makedirs(settings.CHROMA_PERSIST_DIRECTORY, exist_ok=True)
            
            self.chroma_client = chromadb.PersistentClient(
                path=settings.CHROMA_PERSIST_DIRECTORY,
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            
            # Get or create collection
            self.collection = self.chroma_client.get_or_create_collection(
                name="medical_literature",
                metadata={"description": "Medical literature embeddings"}
            )
            
            logger.info(
                "chromadb_initialized",
                persist_directory=settings.CHROMA_PERSIST_DIRECTORY,
                collection_size=self.collection.count()
            )
            
        except Exception as e:
            logger.error("embeddings_initialization_error", error=str(e))
            raise EmbeddingsServiceError(f"Failed to initialize embeddings service: {str(e)}") from e
    
    def create_embedding(self, text: str) -> List[float]:
        """
        Create embedding vector for text.
        
        Args:
            text: Input text to embed
            
        Returns:
            Embedding vector as list of floats
        """
        try:
            embedding = self.model.encode(text, convert_to_numpy=True)
            return embedding.tolist()
        except Exception as e:
            logger.error("embedding_creation_error", error=str(e))
            raise EmbeddingsServiceError(f"Failed to create embedding: {str(e)}") from e
    
    def add_documents(
        self,
        documents: List[Dict[str, Any]],
        correlation_id: str = ""
    ) -> bool:
        """
        Add documents to vector database.
        
        Args:
            documents: List of documents with 'id', 'text', and 'metadata'
            correlation_id: Request tracking ID
            
        Returns:
            True if successful
        """
        try:
            if not documents:
                return True
            
            logger.info(
                "adding_documents_to_vectordb",
                count=len(documents),
                correlation_id=correlation_id,
            )
            
            # Prepare data for ChromaDB
            ids = []
            texts = []
            embeddings = []
            metadatas = []
            
            for doc in documents:
                doc_id = doc.get("id")
                text = doc.get("text")
                metadata = doc.get("metadata", {})
                
                if not doc_id or not text:
                    logger.warning("invalid_document_skipped", doc=doc)
                    continue
                
                # Check if document already exists
                try:
                    existing = self.collection.get(ids=[doc_id])
                    if existing and existing['ids']:
                        logger.debug("document_already_exists", doc_id=doc_id)
                        continue
                except Exception:
                    pass
                
                # Create embedding
                embedding = self.create_embedding(text)
                
                ids.append(doc_id)
                texts.append(text)
                embeddings.append(embedding)
                metadatas.append(metadata)
            
            if ids:
                # Add to ChromaDB
                self.collection.add(
                    ids=ids,
                    embeddings=embeddings,
                    documents=texts,
                    metadatas=metadatas
                )
                
                logger.info(
                    "documents_added_to_vectordb",
                    count=len(ids),
                    correlation_id=correlation_id,
                )
            
            return True
            
        except Exception as e:
            logger.error(
                "add_documents_error",
                error=str(e),
                correlation_id=correlation_id,
            )
            raise EmbeddingsServiceError(f"Failed to add documents: {str(e)}") from e
    
    def search_similar(
        self,
        query: str,
        top_k: int = 10,
        min_score: Optional[float] = None,
        filter_metadata: Optional[Dict[str, Any]] = None,
        correlation_id: str = ""
    ) -> List[Dict[str, Any]]:
        """
        Search for similar documents using vector similarity.
        
        Args:
            query: Search query text
            top_k: Number of results to return
            min_score: Minimum similarity score (0-1)
            filter_metadata: Filter results by metadata
            correlation_id: Request tracking ID
            
        Returns:
            List of similar documents with scores
        """
        try:
            logger.info(
                "vector_search_start",
                query_preview=query[:100],
                top_k=top_k,
                correlation_id=correlation_id,
            )
            
            # Create query embedding
            query_embedding = self.create_embedding(query)
            
            # Search in ChromaDB
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=filter_metadata if filter_metadata else None
            )
            
            # Format results
            similar_docs = []
            
            if results and results['ids'] and results['ids'][0]:
                for i, doc_id in enumerate(results['ids'][0]):
                    # Calculate similarity score (ChromaDB returns distances)
                    # Convert distance to similarity (1 - normalized_distance)
                    distance = results['distances'][0][i] if results.get('distances') else 0
                    similarity = 1 / (1 + distance)  # Convert distance to similarity
                    
                    # Apply minimum score filter
                    if min_score and similarity < min_score:
                        continue
                    
                    doc = {
                        "id": doc_id,
                        "text": results['documents'][0][i] if results.get('documents') else "",
                        "metadata": results['metadatas'][0][i] if results.get('metadatas') else {},
                        "similarity_score": similarity,
                        "distance": distance
                    }
                    
                    similar_docs.append(doc)
            
            logger.info(
                "vector_search_complete",
                results_found=len(similar_docs),
                correlation_id=correlation_id,
            )
            
            return similar_docs
            
        except Exception as e:
            logger.error(
                "vector_search_error",
                error=str(e),
                correlation_id=correlation_id,
            )
            raise EmbeddingsServiceError(f"Vector search failed: {str(e)}") from e
    
    def delete_document(self, doc_id: str) -> bool:
        """Delete document from vector database."""
        try:
            self.collection.delete(ids=[doc_id])
            logger.info("document_deleted", doc_id=doc_id)
            return True
        except Exception as e:
            logger.error("delete_document_error", error=str(e), doc_id=doc_id)
            return False
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about the vector database collection."""
        try:
            count = self.collection.count()
            return {
                "total_documents": count,
                "collection_name": self.collection.name,
                "persist_directory": settings.CHROMA_PERSIST_DIRECTORY,
            }
        except Exception as e:
            logger.error("get_stats_error", error=str(e))
            return {}
    
    def clear_collection(self) -> bool:
        """Clear all documents from collection (use with caution!)."""
        try:
            self.chroma_client.delete_collection(name="medical_literature")
            self.collection = self.chroma_client.create_collection(
                name="medical_literature",
                metadata={"description": "Medical literature embeddings"}
            )
            logger.warning("collection_cleared")
            return True
        except Exception as e:
            logger.error("clear_collection_error", error=str(e))
            return False


# Global instance
embeddings_service = EmbeddingsService()