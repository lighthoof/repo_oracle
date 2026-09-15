from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, HttpUrl

class User(BaseModel):
    id: int
    login: str
    html_url: HttpUrl | None = None

class Comment(BaseModel):
    id: int
    body: str
    user: User
    created_at: datetime
    html_url: HttpUrl | None = None

class Issue(BaseModel):
    number: int
    title: str
    id: int | None = None
    body: str | None = None
    state: Literal["open","closed"]
    user: User
    comments: list[Comment] = Field(default_factory=list)
    html_url: HttpUrl | None = None

class IssueSummary(BaseModel):
    number: int
    state: Literal["OPEN","CLOSED"]
    comments: int = 0

class IssueListPageInfo(BaseModel):
    hasNextPage: bool
    hasPreviousPage: bool
    startCursor: str | None = None
    endCursor: str | None = None

class IssueListPage(BaseModel):
    issues: list[IssueSummary]
    totalCount: int
    pageInfo: IssueListPageInfo

class RepoFile(BaseModel):
    path: str
    html_url: HttpUrl
    content: str

class Chunk(BaseModel):
    text: str
    metadata: dict[str, str | int]

class Citation(BaseModel):
    source_type: Literal["issue", "comment", "readme"] = Field(description="Type of source")
    title: str = Field(description="Short description or issue title for display text")
    url: HttpUrl = Field(description="Direct web URL to the issue or comment")

class AnswerModel(BaseModel):
    answer: str
    citations: list[Citation]
    insufficient_context: bool
    
