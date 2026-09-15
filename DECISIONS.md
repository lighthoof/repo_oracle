1. Did not use agentic flow for ingestion despite MCP being a requirement as it is not a good use case. Straigthforward data retreival is better suited for that
2. Chunking is done using a popular but small model with decent token limit and good precision
3. For vector comparison I use cosine-similarity as decently fast an simple method 