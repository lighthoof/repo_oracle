# Repo Oracle

A small end-to-end RAG/QA system for answering questions about a GitHub repository.

The system:

1. Fetches the repository README, issues, and issue comments through GitHub MCP.
2. Stores raw and validated/parsed data locally.
3. Chunks and embeds the corpus into a persistent Chroma vector database.
4. Retrieves relevant context for a question.
5. Uses PydanticAI with an OpenRouter model to generate a validated answer.
6. Returns source citations and an `insufficient_context` flag when the retrieved context does not support an answer.
7. Evaluates the system against a small golden dataset.

For this assignment, the configured repository is `netbox-community/pynetbox`. The ingestion configuration is repository-independent and can be changed through `.env`.

## Requirements

- Python 3.13+
- [uv](https://docs.astral.sh/uv/)
- Docker
- A GitHub personal access token
- An OpenRouter API key

Docker is required because the ingestion step starts the official GitHub MCP server as a Docker container.

## Setup

Clone the repository and enter the project directory:

```bash
git clone https://github.com/lighthoof/repo_oracle
cd repo-oracle
```

Install the Python dependencies:

```bash
uv sync
```

Create a `.env` file in the project root.

Use the provided environment-variable example as the starting point and configure the GitHub repository, LLM, embedding, and storage settings.

For the assignment, the important GitHub settings are:

```dotenv
GITHUB_PERSONAL_ACCESS_TOKEN=your_github_token
GITHUB_OWNER=netbox-community
GITHUB_REPO=pynetbox
GITHUB_BRANCH=main
GITHUB_FILES=["README.md"]
```

Set your OpenRouter credentials/model as configured in the provided environment example.

## Ingest and index the repository

Run:

```bash
uv run ingest.py
```

This is the main pipeline entry point. It:

1. Starts the GitHub MCP server.
2. Retrieves the configured repository files.
3. Retrieves all open and closed issues.
4. Retrieves comments belonging to those issues.
5. Validates the retrieved data with Pydantic models.
6. Stores raw and parsed data under `data/raw/` and `data/parsed/`.
7. Builds/updates the Chroma vector index from the parsed data.

The ingestion corpus consists only of:

- the configured README file(s);
- open and closed issues;
- comments belonging to those issues.

### Caching

The ingestion step is cache-aware.

If a file or issue already has both its raw and parsed representations locally, it is skipped on subsequent ingestion runs instead of being fetched again.

The first run may take some time because it downloads the repository data and starts the GitHub MCP Docker container.

The Chroma database is also generated locally. It does not need to be committed to the repository.

## Run the evaluation

After ingestion and indexing, run:

```bash
uv run eval.py
```

The evaluation:

- loads and validates `golden.json`;
- retrieves context for each test question;
- generates a structured answer;
- validates the generated response;
- checks the expected answer characteristics;
- checks whether expected sources were retrieved;
- reports retrieval accuracy and answer accuracy separately.

Example output:

```text
Question: what is pynetbox for?
  Retrieval hit: True
  Answer correct: True
  insufficient_context: False

...

Retrieval accuracy: 6/7 (85.7%)
Answer accuracy: 9/10 (90.0%)
```

The exact answer accuracy may vary between runs because the assignment uses the `openrouter/free` model. Retrieval and generation are evaluated separately so this distinction is visible.

## Ask your own question

Run:

```bash
uv run ask.py "what is pynetbox for?"
```

The command prints a representation of AnswerModel object, that contains:

- the generated answer;
- relevant citations;
- the `insufficient_context` value.

For a question supported by the repository, the answer should include a repository source URL, for example:

```text
  "citations": [
    "https://github.com/netbox-community/pynetbox/blob/main/README.md"
  ],
  "insufficient_context": false
```

For information that is not supported by the retrieved repository context, the model is instructed not to use outside knowledge or invent citations.

For example:

```bash
uv run ask.py "how do i install netbox?"
```

This information is not contained in the indexed corpus, so the expected behavior is:

```text
"insufficient_context": true
```

It should be treated as insufficient context rather than answered using outside knowledge.

## Project structure

```text
.
├── ask.py          # Retrieval + LLM question answering
├── config.py       # Pydantic settings
├── eval.py         # Golden-set evaluation
├── golden.json     # Assignment-specific evaluation questions
├── index.py        # Chunking, embeddings, and Chroma indexing
├── ingest.py       # GitHub MCP ingestion + indexing pipeline
├── models.py       # Pydantic data models
├── pyproject.toml  # Project metadata and dependencies
├── data/
│   ├── raw/        # Raw GitHub/MCP responses
│   └── parsed/     # Validated/parsed data
└── chroma_db/      # Locally generated persistent vector database
```

`golden.json` is intentionally specific to the `pynetbox` assignment. The ingestion and QA pipeline itself is configurable for other GitHub repositories through `.env`.

## Typical workflow

From a clean clone:

```bash
uv sync
```

Configure `.env`, then run:

```bash
uv run ingest.py
uv run eval.py
```

To query the system directly:

```bash
uv run ask.py "what is pynetbox for?"
```

Repository data and the Chroma database are persisted locally. On later ingestion runs, cached raw/parsed repository data is reused instead of fetching every file and issue again.