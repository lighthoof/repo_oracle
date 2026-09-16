1. Did not use agentic flow for ingestion despite MCP being a requirement. Straightforward data retrieval is better suited to a deterministic pipeline
2. Used a small, popular embedding model with decent token limit and good precision for the corpus
3. Used cosine similarity for vector comparison as simple an sufficiently fast approach
4. Source URLs come from Chroma, not LLM answers, to prevent a model hallucinating document links

A chunk is a section of an issue thread limited by token size, with overlap between consecutive chunks. This provides sufficient context while keeping retrieval units focused and the overall setup simple