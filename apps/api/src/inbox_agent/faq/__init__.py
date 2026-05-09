"""FAQ ingestion + retrieval pipeline."""

from inbox_agent.faq.embed import EmbeddingClient, get_embedding_client
from inbox_agent.faq.ingest import FAQIngestor, IngestResult
from inbox_agent.faq.retrieve import FAQRetriever

__all__ = [
    "EmbeddingClient",
    "FAQIngestor",
    "FAQRetriever",
    "IngestResult",
    "get_embedding_client",
]
