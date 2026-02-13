"""
RAG Service - Orchestrates Retrieval-Augmented Generation
Combines PubMed search, embeddings, and clinical guidelines
"""
from typing import List, Dict, Any, Optional
import asyncio
import json
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.pubmed_service import pubmed_service, PubMedServiceError
from app.services.embeddings_service import embeddings_service, EmbeddingsServiceError
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class RAGServiceError(Exception):
    """RAG service exception."""
    pass


class RAGService:
    """
    Retrieval-Augmented Generation Service.
    
    Orchestrates:
    1. Medical literature retrieval (PubMed)
    2. Vector similarity search (ChromaDB)
    3. Clinical guidelines integration
    4. Evidence ranking and selection
    """
    
    def __init__(self):
        """Initialize RAG service."""
        self.pubmed = pubmed_service
        self.embeddings = embeddings_service
        self.guidelines_cache = {}  # In-memory cache for guidelines
    
    async def retrieve_evidence(
        self,
        chief_complaint: str,
        symptoms: List[str],
        patient_age: int,
        patient_gender: str,
        medical_history: Optional[Dict[str, Any]] = None,
        correlation_id: str = ""
    ) -> Dict[str, Any]:
        """
        Retrieve medical evidence for diagnosis.
        
        Args:
            chief_complaint: Main complaint
            symptoms: List of symptoms
            patient_age: Patient age
            patient_gender: Patient gender
            medical_history: Patient medical history
            correlation_id: Request tracking ID
            
        Returns:
            Dictionary containing evidence from multiple sources
        """
        try:
            logger.info(
                "rag_evidence_retrieval_start",
                chief_complaint=chief_complaint,
                symptoms_count=len(symptoms),
                correlation_id=correlation_id,
            )
            
            # Build search query
            search_query = self._build_search_query(
                chief_complaint, symptoms, patient_age, patient_gender
            )
            
            # Parallel retrieval from multiple sources
            pubmed_task = self._retrieve_from_pubmed(search_query, correlation_id)
            vector_task = self._retrieve_from_vectordb(search_query, correlation_id)
            guidelines_task = self._retrieve_guidelines(symptoms, correlation_id)
            
            # Execute in parallel
            pubmed_results, vector_results, guidelines = await asyncio.gather(
                pubmed_task,
                vector_task,
                guidelines_task,
                return_exceptions=True
            )
            
            # Handle exceptions
            if isinstance(pubmed_results, Exception):
                logger.error("pubmed_retrieval_failed", error=str(pubmed_results))
                pubmed_results = []
            
            if isinstance(vector_results, Exception):
                logger.error("vector_retrieval_failed", error=str(vector_results))
                vector_results = []
            
            if isinstance(guidelines, Exception):
                logger.error("guidelines_retrieval_failed", error=str(guidelines))
                guidelines = []
            
            # Combine and rank evidence
            combined_evidence = self._combine_and_rank_evidence(
                pubmed_results=pubmed_results,
                vector_results=vector_results,
                guidelines=guidelines
            )

            if db:  # Only if database session available
                combined_evidence = await self._apply_feedback_boost(combined_evidence, db)
            
            logger.info(
                "rag_evidence_retrieval_complete",
                pubmed_count=len(pubmed_results),
                vector_count=len(vector_results),
                guidelines_count=len(guidelines),
                total_evidence=len(combined_evidence),
                correlation_id=correlation_id,
            )
            
            # Index new articles synchronously
            if pubmed_results:
                try:
                    documents = []
                    for article in pubmed_results:
                        pmid = article.get("pubmed_id")
                        if not pmid:
                            continue
            
                        text = f"{article.get('title', '')} {article.get('abstract', '')}"
                        doc = {
                            "id": f"pubmed_{pmid}",
                            "text": text,
                            "metadata": {
                                "pubmed_id": pmid,
                                "title": article.get("title", ""),
                                "authors": article.get("authors", ""),
                                "journal": article.get("journal", ""),
                                "publication_year": article.get("publication_year"),
                                "url": article.get("url", ""),
                                "evidence_type": article.get("evidence_type", "research")
                            }
                        }
                        documents.append(doc)
        
                    if documents:
                        embeddings_service.add_documents(documents, correlation_id)
                except Exception as e:
                    logger.warning("article_indexing_failed", error=str(e)) 

            return {
                "evidence": combined_evidence,
                "sources": {
                    "pubmed": len(pubmed_results),
                    "vectordb": len(vector_results),
                    "guidelines": len(guidelines)
                },
                "search_query": search_query
            }
            
        except Exception as e:
            logger.error(
                "rag_evidence_retrieval_error",
                error=str(e),
                correlation_id=correlation_id,
            )
            raise RAGServiceError(f"Evidence retrieval failed: {str(e)}") from e
    
    def _build_search_query(
        self,
        chief_complaint: str,
        symptoms: List[str],
        patient_age: int,
        patient_gender: str
    ) -> str:
        """Build optimized search query for medical literature."""
        # Combine chief complaint and symptoms
        symptom_text = " ".join(symptoms)
        
        # Add age group context
        age_group = self._get_age_group(patient_age)
        
        # Build query
        query = f"{chief_complaint} {symptom_text}"
        
        # Add context
        if age_group:
            query += f" {age_group}"
        
        if patient_gender:
            query += f" {patient_gender}"
        
        return query.strip()
    
    def _get_age_group(self, age: int) -> str:
        """Get age group category."""
        if age < 2:
            return "infant"
        elif age < 12:
            return "child"
        elif age < 18:
            return "adolescent"
        elif age < 65:
            return "adult"
        else:
            return "elderly"
    
    async def _retrieve_from_pubmed(
        self, query: str, correlation_id: str
    ) -> List[Dict[str, Any]]:
        """Retrieve articles from PubMed."""
        try:
            articles = await self.pubmed.search_articles(
                query=query,
                max_results=settings.PUBMED_MAX_RESULTS,
                correlation_id=correlation_id
            )
            
            # Add source information
            for article in articles:
                article["source"] = "pubmed"
                article["relevance_score"] = 0.9  # High relevance (newly fetched)
            
            return articles
            
        except Exception as e:
            logger.error("pubmed_retrieval_error", error=str(e))
            return []
    
    async def _retrieve_from_vectordb(
        self, query: str, correlation_id: str
    ) -> List[Dict[str, Any]]:
        """Retrieve similar documents from vector database."""
        try:
            results = embeddings_service.search_similar(
                query=query,
                top_k=10,
                min_score=settings.MIN_EVIDENCE_SCORE,
                correlation_id=correlation_id
            )
            
            # Format results
            formatted = []
            for result in results:
                metadata = result.get("metadata", {})
                formatted.append({
                    "pubmed_id": metadata.get("pubmed_id"),
                    "title": metadata.get("title", ""),
                    "authors": metadata.get("authors", ""),
                    "journal": metadata.get("journal", ""),
                    "publication_year": metadata.get("publication_year"),
                    "abstract": result.get("text", ""),
                    "url": metadata.get("url", ""),
                    "evidence_type": metadata.get("evidence_type", "research"),
                    "source": "vectordb",
                    "relevance_score": result.get("similarity_score", 0.5)
                })
            
            return formatted
            
        except Exception as e:
            logger.error("vectordb_retrieval_error", error=str(e))
            return []
    
    async def _apply_feedback_boost(
            self, evidence: List[Dict], db: AsyncSession
            ) -> List[Dict]:
        """Boost evidence from sources that historically led to correct diagnoses."""
        try:
            from app.services.feedback_analytics_service import feedback_analytics_service
        
            # Get effectiveness scores
            effectiveness = await feedback_analytics_service.get_evidence_effectiveness(db)
        
            # Boost relevance scores based on source effectiveness
            for item in evidence:
                journal = item.get("journal", "Unknown")
                if journal in effectiveness:
                    boost = effectiveness[journal]  # 0.0 to 1.0
                    original_score = item.get("relevance_score", 0.5)
                    # Apply 20% boost for highly effective sources
                    item["relevance_score"] = min(1.0, original_score * (1 + boost * 0.2))
        
            return evidence
        except Exception as e:
            logger.warning("feedback_boost_failed", error=str(e))
            return evidence
    
    async def _retrieve_guidelines(
        self, symptoms: List[str], correlation_id: str
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant clinical guidelines."""
        try:
            # In production, this would query a guidelines database
            # For now, return predefined common guidelines
            
            guidelines = []
            
            # Example: Respiratory symptoms
            respiratory_symptoms = {"cough", "fever", "shortness of breath", "chest pain"}
            if any(s.lower() in respiratory_symptoms for s in symptoms):
                guidelines.append({
                    "title": "Community-Acquired Pneumonia Guidelines",
                    "source": "IDSA/ATS",
                    "url": "https://www.thoracic.org/statements/resources/mtpi/cap.pdf",
                    "evidence_type": "guideline",
                    "relevance_score": 0.95,
                    "summary": "Evidence-based guidelines for diagnosis and treatment of CAP"
                })
            
            # Example: Cardiac symptoms
            cardiac_symptoms = {"chest pain", "shortness of breath", "palpitations"}
            if any(s.lower() in cardiac_symptoms for s in symptoms):
                guidelines.append({
                    "title": "Acute Coronary Syndrome Guidelines",
                    "source": "ACC/AHA",
                    "url": "https://www.acc.org/guidelines",
                    "evidence_type": "guideline",
                    "relevance_score": 0.95,
                    "summary": "Guidelines for management of acute coronary syndromes"
                })
            
            # Add source
            for guideline in guidelines:
                guideline["source"] = "guidelines"
            
            logger.info(
                "guidelines_retrieved",
                count=len(guidelines),
                correlation_id=correlation_id,
            )
            
            return guidelines
            
        except Exception as e:
            logger.error("guidelines_retrieval_error", error=str(e))
            return []
    
    def _combine_and_rank_evidence(
        self,
        pubmed_results: List[Dict[str, Any]],
        vector_results: List[Dict[str, Any]],
        guidelines: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Combine evidence from all sources and rank by relevance.
        """
        all_evidence = []
        seen_ids = set()
        
        # Add guidelines first (highest priority)
        for guideline in guidelines:
            all_evidence.append(guideline)
        
        # Add PubMed results
        for article in pubmed_results:
            pmid = article.get("pubmed_id")
            if pmid and pmid not in seen_ids:
                all_evidence.append(article)
                seen_ids.add(pmid)
        
        # Add vector DB results (avoid duplicates)
        for article in vector_results:
            pmid = article.get("pubmed_id")
            if pmid and pmid not in seen_ids:
                all_evidence.append(article)
                seen_ids.add(pmid)
        
        # Sort by relevance score (descending)
        all_evidence.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
        
        # Limit to top results
        max_evidence = settings.PUBMED_MAX_RESULTS + len(guidelines)
        return all_evidence[:max_evidence]
    
    async def _index_new_articles(
        self, articles: List[Dict[str, Any]], correlation_id: str
    ):
        """Index new PubMed articles in vector database for future use."""
        try:
            documents = []
            
            for article in articles:
                pmid = article.get("pubmed_id")
                if not pmid:
                    continue
                
                # Create document for indexing
                text = f"{article.get('title', '')} {article.get('abstract', '')}"
                
                doc = {
                    "id": f"pubmed_{pmid}",
                    "text": text,
                    "metadata": {
                        "pubmed_id": pmid,
                        "title": article.get("title", ""),
                        "authors": article.get("authors", ""),
                        "journal": article.get("journal", ""),
                        "publication_year": article.get("publication_year"),
                        "url": article.get("url", ""),
                        "evidence_type": article.get("evidence_type", "research")
                    }
                }
                
                documents.append(doc)
            
            if documents:
                embeddings_service.add_documents(documents, correlation_id)
                logger.info(
                    "articles_indexed",
                    count=len(documents),
                    correlation_id=correlation_id,
                )
            
        except Exception as e:
            logger.error("article_indexing_error", error=str(e))
    
    def format_evidence_for_llm(
        self, evidence: List[Dict[str, Any]], max_citations: int = 5
    ) -> str:
        """
        Format evidence for inclusion in LLM prompt.
        
        Args:
            evidence: List of evidence documents
            max_citations: Maximum citations to include
            
        Returns:
            Formatted evidence text for LLM
        """
        if not evidence:
            return "No specific medical literature found for this case."
        
        formatted = "## Relevant Medical Evidence:\n\n"
        
        for i, item in enumerate(evidence[:max_citations], 1):
            evidence_type = item.get("evidence_type", "research").upper()
            title = item.get("title", "Unknown")
            authors = item.get("authors", "Unknown authors")
            journal = item.get("journal", "")
            year = item.get("publication_year", "")
            source = item.get("source", "")
            relevance = item.get("relevance_score", 0)
            
            formatted += f"### [{i}] {evidence_type}\n"
            formatted += f"**Title:** {title}\n"
            formatted += f"**Authors:** {authors}\n"
            
            if journal:
                formatted += f"**Journal:** {journal}"
                if year:
                    formatted += f" ({year})"
                formatted += "\n"
            
            # Add abstract/summary if available
            abstract = item.get("abstract", item.get("summary", ""))
            if abstract:
                # Truncate long abstracts
                if len(abstract) > 500:
                    abstract = abstract[:500] + "..."
                formatted += f"**Summary:** {abstract}\n"
            
            formatted += f"**Relevance Score:** {relevance:.2f}\n"
            formatted += f"**Source:** {source}\n\n"
        
        return formatted


# Global instance
rag_service = RAGService()