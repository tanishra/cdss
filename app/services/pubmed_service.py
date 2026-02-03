"""
PubMed Service - Retrieve medical literature from PubMed
"""
from typing import List, Dict, Any, Optional
import aiohttp
from Bio import Entrez
import asyncio
from datetime import datetime

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Set PubMed email (required by NCBI)
Entrez.email = settings.PUBMED_API_EMAIL


class PubMedServiceError(Exception):
    """PubMed service exception."""
    pass


class PubMedService:
    """Service for retrieving medical literature from PubMed."""
    
    BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    
    async def search_articles(
        self,
        query: str,
        max_results: int = 10,
        correlation_id: str = ""
    ) -> List[Dict[str, Any]]:
        """
        Search PubMed for relevant articles.
        
        Args:
            query: Search query (symptoms, condition, etc.)
            max_results: Maximum number of results
            correlation_id: Request tracking ID
            
        Returns:
            List of article metadata
        """
        try:
            logger.info(
                "pubmed_search_start",
                query=query,
                max_results=max_results,
                correlation_id=correlation_id,
            )
            
            # Step 1: Search for PMIDs
            pmids = await self._search_pmids(query, max_results)
            
            if not pmids:
                logger.warning("pubmed_no_results", query=query)
                return []
            
            # Step 2: Fetch article details
            articles = await self._fetch_article_details(pmids)
            
            logger.info(
                "pubmed_search_complete",
                articles_found=len(articles),
                correlation_id=correlation_id,
            )
            
            return articles
            
        except Exception as e:
            logger.error(
                "pubmed_search_error",
                error=str(e),
                query=query,
                correlation_id=correlation_id,
            )
            raise PubMedServiceError(f"PubMed search failed: {str(e)}") from e
    
    async def _search_pmids(self, query: str, max_results: int) -> List[str]:
        """Search PubMed and get PMIDs."""
        try:
            # Build search query
            search_query = f"{query} AND (systematic review[pt] OR meta-analysis[pt] OR clinical trial[pt])"
            
            # Use async HTTP request
            params = {
                "db": "pubmed",
                "term": search_query,
                "retmax": max_results,
                "retmode": "json",
                "sort": "relevance"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.BASE_URL}/esearch.fcgi",
                    params=params
                ) as response:
                    if response.status != 200:
                        raise PubMedServiceError(f"PubMed API error: {response.status}")
                    
                    data = await response.json()
                    pmids = data.get("esearchresult", {}).get("idlist", [])
                    
                    return pmids
                    
        except Exception as e:
            logger.error("pubmed_search_pmids_error", error=str(e))
            raise
    
    async def _fetch_article_details(self, pmids: List[str]) -> List[Dict[str, Any]]:
        """Fetch full article details for given PMIDs."""
        try:
            if not pmids:
                return []
            
            # Fetch details
            params = {
                "db": "pubmed",
                "id": ",".join(pmids),
                "retmode": "xml"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.BASE_URL}/efetch.fcgi",
                    params=params
                ) as response:
                    if response.status != 200:
                        raise PubMedServiceError(f"PubMed fetch error: {response.status}")
                    
                    xml_data = await response.text()
                    
                    # Parse XML (simplified - in production use proper XML parser)
                    articles = self._parse_pubmed_xml(xml_data, pmids)
                    
                    return articles
                    
        except Exception as e:
            logger.error("pubmed_fetch_details_error", error=str(e))
            return []
    
    def _parse_pubmed_xml(self, xml_data: str, pmids: List[str]) -> List[Dict[str, Any]]:
        """Parse PubMed XML response."""
        from xml.etree import ElementTree as ET
        
        articles = []
        
        try:
            root = ET.fromstring(xml_data)
            
            for article_elem in root.findall(".//PubmedArticle"):
                try:
                    # Extract article info
                    pmid_elem = article_elem.find(".//PMID")
                    pmid = pmid_elem.text if pmid_elem is not None else None
                    
                    title_elem = article_elem.find(".//ArticleTitle")
                    title = title_elem.text if title_elem is not None else "No title"
                    
                    abstract_elem = article_elem.find(".//AbstractText")
                    abstract = abstract_elem.text if abstract_elem is not None else ""
                    
                    # Authors
                    authors = []
                    for author_elem in article_elem.findall(".//Author"):
                        last_name = author_elem.find("LastName")
                        first_name = author_elem.find("ForeName")
                        if last_name is not None:
                            author_name = last_name.text
                            if first_name is not None:
                                author_name = f"{first_name.text} {author_name}"
                            authors.append(author_name)
                    
                    # Journal
                    journal_elem = article_elem.find(".//Journal/Title")
                    journal = journal_elem.text if journal_elem is not None else ""
                    
                    # Publication year
                    year_elem = article_elem.find(".//PubDate/Year")
                    year = int(year_elem.text) if year_elem is not None else None
                    
                    # DOI
                    doi_elem = article_elem.find(".//ArticleId[@IdType='doi']")
                    doi = doi_elem.text if doi_elem is not None else None
                    
                    article = {
                        "pubmed_id": pmid,
                        "title": title,
                        "authors": ", ".join(authors[:3]) if authors else "Unknown",
                        "journal": journal,
                        "publication_year": year,
                        "doi": doi,
                        "abstract": abstract,
                        "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else None,
                        "evidence_type": "research"
                    }
                    
                    articles.append(article)
                    
                except Exception as e:
                    logger.warning("article_parse_error", error=str(e))
                    continue
            
            return articles
            
        except Exception as e:
            logger.error("xml_parse_error", error=str(e))
            return []


# Global instance
pubmed_service = PubMedService()