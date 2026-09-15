import json
import os
import chromadb
import hashlib

from config import settings
from pathlib import Path
from models import Issue, Chunk, RepoFile

from sentence_transformers import SentenceTransformer

model = SentenceTransformer(settings.embedding_model_name)

def load_parsed_data(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))

def chunk_text(text: str, max_tokens: int = 250, overlap: int = 40) -> list[str]:
    tokens = model.tokenizer.backend_tokenizer.encode(text, add_special_tokens=False).ids
    chunks = []
    
    start = 0
    while start < len(tokens):
        end = min(start + max_tokens, len(tokens))
        chunk_tokens = tokens[start:end]

        chunks.append(
            model.tokenizer.decode(
                chunk_tokens, 
                skip_special_tokens=True
            )
        )

        if end == len(tokens):
            break
        start += (max_tokens - overlap)
        
    return chunks

def chunk_issue(issue: Issue) -> list[Chunk]:
    chunks = []
    num = issue.number
    title = issue.title
    header = f"Github issue #{num}: {title}\n"

    body_text = issue.body or "No description provided"
    for subtext in chunk_text(body_text, settings.max_tokens, settings.overlap):
        chunks.append(
            Chunk(
                text= f"{header}Description:\n{subtext}",
                metadata= {
                    "type": "issue_body",
                    "issue_number": num,
                    "url": str(issue.html_url) if issue.html_url else ""
                }
            )
        )


    comments = issue.comments
    if comments:
        for comment in comments:
            comment_text = (
                f"{header}\n"
                f"Comment by {comment.user.login}:\n"
                f"{comment.body}"
            )

            for subtext in chunk_text(comment_text, settings.max_tokens, settings.overlap):
                chunks.append(
                    Chunk(
                        text= f"{header}Comments:\n{subtext}",
                        metadata= {
                            "type": "issue_comments",
                            "issue_number": num,
                            "comment_id": comment.id,
                            "url": str(issue.html_url) if issue.html_url else ""
                        }
                    )
                )
    
    return chunks

def chunk_file(file: RepoFile) -> list[Chunk]:
    chunks = []
    sections = file.content.split("\n## ")
    
    for idx, sec in enumerate(sections):
        section_text = sec if idx == 0 else f"## {sec}"
        first_line = section_text.split("\n")[0].replace("#", "").strip()
        header = f"File: {file.path} | Section: {first_line}\n"
        
        for subtext in chunk_text(section_text, settings.max_tokens, settings.overlap):
            chunks.append(
                Chunk(
                    text= f"{header}{subtext}",
                    metadata= {
                        "type": "readme",
                        "path": file.path,
                        "section": first_line,
                        "url": str(file.html_url) if file.html_url else ""
                    }
                )
            )
            
    return chunks

def generate_chunk_id(chunk: Chunk) -> str:
    content = json.dumps(
        {
            "text": chunk.text,
            "metadata": chunk.metadata,
        },
        sort_keys=True,
    )
    return hashlib.sha256(content.encode("utf-8")).hexdigest()

def main():
    file_path = Path(f"{settings.parsed_data_dir}/files")
    issue_path = Path(f"{settings.parsed_data_dir}/issues")
    stored_file_list = os.listdir(file_path)
    stored_issue_list = os.listdir(issue_path)

    # Load and chunk the data
    chunks = []
    for stored_file_name in stored_file_list:
        stored_file_path = file_path / stored_file_name

        file = load_parsed_data(stored_file_path)
        validated_file = RepoFile.model_validate(file)

        file_chunks = chunk_file(validated_file)
        chunks.extend(file_chunks)

    for stored_issue_name in stored_issue_list:
        stored_issue_path = issue_path / stored_issue_name

        issue = load_parsed_data(stored_issue_path)
        validated_issue = Issue.model_validate(issue)

        issue_chunks = chunk_issue(validated_issue)
        chunks.extend(issue_chunks)

    # Prepare embeddings and IDs
    texts = [chunk.text for chunk in chunks]
    
    embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=True)
    chunk_ids = [generate_chunk_id(chunk) for chunk in chunks]

    # Load data into chroma db
    chroma_client = chromadb.PersistentClient(path=settings.vector_db_path)
    collection = chroma_client.get_or_create_collection(
        name="vector_data", 
        metadata={"hnsw:space": "cosine"},
    )

    collection.upsert(
        ids=chunk_ids,
        documents=[chunk.text for chunk in chunks],
        embeddings=embeddings.tolist(),
        metadatas=[chunk.metadata for chunk in chunks],
    )

    print(f"Chroma collection contains {collection.count()} chunks")

def run_index():
    main()

if __name__ == "__main__":
    run_index()