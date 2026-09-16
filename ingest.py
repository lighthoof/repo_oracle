import json
import anyio

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from config import settings
from models import Issue, IssueListPage, RepoFile, Comment


def setup_directories():
    (settings.raw_data_dir / "files").mkdir(parents=True, exist_ok=True)
    (settings.raw_data_dir / "issues").mkdir(parents=True, exist_ok=True)
    (settings.raw_data_dir / "comments").mkdir(parents=True, exist_ok=True)
    (settings.parsed_data_dir / "files").mkdir(parents=True, exist_ok=True)
    (settings.parsed_data_dir / "issues").mkdir(parents=True, exist_ok=True)

async def get_all_issue_summaries(session: ClientSession):
    summaries = []
    cursor = ""

    while True:
        page = await session.call_tool(
                    "list_issues",
                    arguments={
                        "owner": settings.github_owner,
                        "repo": settings.github_repo,
                        "state": "all",
                        "after": cursor
                    }
                )

        raw_issue_page = json.loads("\n".join([c.text for c in page.content if c.type == "text"]))     
        validated_issue_page = IssueListPage.model_validate(raw_issue_page)   
        summaries.extend(validated_issue_page.issues)

        if not validated_issue_page.pageInfo.hasNextPage:
            break

        if validated_issue_page.pageInfo.endCursor is None:
            raise RuntimeError("MCP returned hasNextPage=True without an endCursor")

        cursor = validated_issue_page.pageInfo.endCursor

    return summaries

def is_file_cached(slug: str) -> bool:
    raw_exists = (settings.raw_data_dir / "files" / f"{slug}.json").exists()
    parsed_exists = (settings.parsed_data_dir / "files" / f"{slug}.json").exists()

    return raw_exists and parsed_exists


def is_issue_cached(issue_num: int) -> bool:
    raw_issue_exists = (settings.raw_data_dir / "issues" / f"issue_{issue_num}.json").exists()
    raw_comments_exists = (settings.raw_data_dir / "comments" / f"issue_{issue_num}_comments.json").exists()
    parsed_exists = (settings.parsed_data_dir / "issues" / f"issue_{issue_num}.json" ).exists()

    return raw_issue_exists and raw_comments_exists and parsed_exists

async def ingest_file(file_path: str, session: ClientSession):
    slug = file_path.replace("/", "_").replace(".", "_")

    if is_file_cached(slug):
        print(f"- Skipping cached file: {file_path}")
        return

    print(f"### Fetching file via MCP: {file_path}")
    result = await session.call_tool(
        "get_file_contents",
        arguments={
            "owner": settings.github_owner,
            "repo": settings.github_repo,
            "path": file_path,
            "ref": settings.github_branch,
        }
    )
                
    text = extract_file_content(result)

    raw_payload = {
        "path": file_path,
        "content": text
    }

    # Save raw API response
    raw_path = settings.raw_data_dir / "files" / f"{slug}.json"
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(raw_payload, f, indent=2)

    # Save validated data
    file_obj = RepoFile(
        path=file_path,
        html_url=f"https://github.com/{settings.github_owner}/{settings.github_repo}/blob/{settings.github_branch}/{file_path}",
        content=text
    )
    parsed_path = settings.parsed_data_dir / "files" / f"{slug}.json"
    with open(parsed_path, "w", encoding="utf-8") as f:
        f.write(file_obj.model_dump_json(indent=2))

async def ingest_issue(issue_num: int, session: ClientSession):
    if is_issue_cached(issue_num):
        print(f"- Skipping cached issue #{issue_num}")
        return

    print(f"### Fetching issue #{issue_num} via MCP...")
    issue_res = await session.call_tool(
        "issue_read",
        arguments={
            "method": "get",
            "owner": settings.github_owner,
            "repo": settings.github_repo,
            "issue_number": issue_num
        }
    )

    raw_issue = json.loads("\n".join([c.text for c in issue_res.content if c.type == "text"]))

    # Fetch issue comments
    comments_res = await session.call_tool(
        "issue_read",
        arguments={
            "method": "get_comments",
            "owner": settings.github_owner,
            "repo": settings.github_repo,
            "issue_number": issue_num
        }
    )
    comments_text = "\n".join([c.text for c in comments_res.content if c.type == "text"])
    raw_comments = json.loads(comments_text) if comments_text.strip() else []

    # Save raw API response
    raw_issue_path = settings.raw_data_dir / "issues" / f"issue_{issue_num}.json"
    with open(raw_issue_path, "w", encoding="utf-8") as f:
        json.dump(raw_issue, f, indent=2, default=str)
    
    raw_comments_path = settings.raw_data_dir / "comments" / f"issue_{issue_num}_comments.json"
    with open(raw_comments_path, "w", encoding="utf-8") as f:
        json.dump(raw_comments, f, indent=2, default=str)

    validated_comments = [Comment.model_validate(comment) for comment in raw_comments]
    enriched_issue = dict(raw_issue)
    enriched_issue["comments"] = validated_comments 

    # Save validated data
    validated_issue = Issue.model_validate(enriched_issue)
    parsed_issue_path = settings.parsed_data_dir / "issues" / f"issue_{issue_num}.json"
    with open(parsed_issue_path, "w", encoding="utf-8") as f:
        f.write(validated_issue.model_dump_json(indent=2))

def extract_file_content(result) -> str:
    for content in result.content:
        # Regular MCP text content
        if getattr(content, "type", None) == "text":
            text = getattr(content, "text", "")
            
            # Don't mistake the status message for file content
            if text and not text.startswith("successfully downloaded text file"):
                return text

        # EmbeddedResource returned by GitHub MCP
        resource = getattr(content, "resource", None)

        if resource is not None:
            resource_text = getattr(resource, "text", None)

            if resource_text is not None:
                return resource_text

    raise RuntimeError(
        f"Could not extract file content from MCP response: {result.content!r}"
    )

async def main():
    setup_directories()
    token_val = settings.github_personal_access_token.get_secret_value()
    server_params = StdioServerParameters(
        command="docker",
        args=[
            "run", "-i", "--rm",
            "-e", "GITHUB_PERSONAL_ACCESS_TOKEN",
            "ghcr.io/github/github-mcp-server:latest",
        ],
        env={"GITHUB_PERSONAL_ACCESS_TOKEN": token_val}
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            target_files = settings.github_files
            for file_path in target_files:
                await ingest_file(file_path, session)

            target_issues = await get_all_issue_summaries(session)
            for issue in target_issues:
                await ingest_issue(issue.number, session)
                
    # Build/update the vector index after ingestion is complete.
    from index import run_index
    run_index()

def run_ingestion():
    anyio.run(main)

if __name__ == "__main__":
    run_ingestion()