1. Did not use agentic flow for ingestion despite MCP being a requirement. Straigthforward data retreival is better suited to a deterministic pipeline
2. Used a amsll, popular embedding model with decent token limit and good precision for the corpus
3. Use cosine similarity for vector comparison as simple an sufficently fast approach
4. Source URLs come from Chroma, not LLM answers, to prevent a model hallucinating document links