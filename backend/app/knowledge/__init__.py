"""Ingestion pipeline for the Lenny knowledge base (Phase 4).

This package is offline/CLI-only (``python -m app.knowledge.ingest``) -
nothing here runs as part of the FastAPI request path. The online
counterpart that reads what this package writes is
``app.services.knowledge_retriever.KnowledgeRetriever``.
"""
