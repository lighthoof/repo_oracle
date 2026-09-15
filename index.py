import json
from config import settings
from pathlib import Path
from sentence_transformers import SentenceTransformer

model = SentenceTransformer(settings.embedding_model_name)
tokenizer = model.tokenizer

def load_parsed_data(path: Path) -> str:
    return path.read_text(encoding="utf-8")

def count_tokens(text: str):
    tokens = model.tokenizer.encode(text, add_special_tokens=True)
    total_tokens = len(tokens)
    max_length = model.max_seq_length  # Automatically gets 384 for all-mpnet-base-v2

    return tokens

def chunk_text(text: str, max_tokens: int = 300, overlap: int = 40) -> list[str]:
    tokens = tokenizer.encode(text, add_special_tokens=False)
    chunks = []
    
    start = 0
    while start < len(tokens):
        end = min(start + max_tokens, len(tokens))
        chunk_tokens = tokens[start:end]
        chunks.append(tokenizer.decode(chunk_tokens, skip_special_tokens=True))
        if end == len(tokens):
            break
        start += (max_tokens - overlap)
        
    return chunks

def chunk_issue(issue: dict) -> list[dict]:
    chunks = []
    num = issue.get("number","")
    title = issue.get("title","")
    header = f"Github issue #{num}: {title}\n"

    body_text = issue.get("body","") or "No description provided"
    for subtext in chunk_text(body_text, max_tokens=250):
        chunks.append({
            "text": f"{header}Description:\n{sub_text}",
            "metadata": {"type": "issue_body", "issue_number": num, "url": issue.get("html_url")}
        })

    comments = issue.get("comments",[])
    if comments:
        comment_str = "\n".join([f"- {c['user']['login']}: {c['body']}" for c in comments])

        for subtext in chunk_text(comment_str, max_tokens=250):
            chunks.append({
                "text": f"{header}Comments:\n{sub_text}",
                "metadata": {"type": "issue_comments", "issue_number": num, "url": issue.get("html_url")}
            })
    
    return chunks

def chunk_readme(file_path: str, content: str) -> list[dict]:
    """Chunks README.md by sections while enforcing token bounds."""
    chunks = []
    sections = content.split("\n## ")
    
    for idx, sec in enumerate(sections):
        section_text = sec if idx == 0 else f"## {sec}"
        first_line = section_text.split("\n")[0].replace("#", "").strip()
        header = f"File: {file_path} | Section: {first_line}\n"
        
        for sub_text in chunk_text(section_text, max_tokens=250):
            chunks.append({
                "text": f"{header}{sub_text}",
                "metadata": {"type": "readme", "path": file_path, "section": first_line}
            })
            
    return chunks

#path = Path("data/parsed/files/README_md.json")
#text = json.loads(load_parsed_data(path))["content"]
#chunks = chunk_text(text)
#tokens = count_tokens(text)

#print(f"Text length: {len(text)}")
#print(f"Chunks: {len(chunks)}")
#print(f"Tokens: {len(tokens)}")