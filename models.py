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

class LLMAnswer(BaseModel):
    answer: str
    source_ids: list[int]
    insufficient_context: bool

class AnswerModel(BaseModel):
    answer: str
    citations: list[HttpUrl]
    insufficient_context: bool

class TestCase(BaseModel):
    query: str
    expected_keywords: list[str]
    expected_citations: list[str]
    insufficient_context: bool

class GoldenDataset(BaseModel):
    test_cases: list[TestCase]
