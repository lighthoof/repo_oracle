import argparse
import chromadb
import os

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openrouter import OpenRouterProvider
from pydantic_ai.exceptions import UnexpectedModelBehavior
from sentence_transformers import SentenceTransformer

from models import AnswerModel, LLMAnswer
from config import settings

SYSTEM_PROMPT = """
You answer questions using ONLY the retrieved repository context.

Rules:
- Do not use outside knowledge.
- Do not invent facts, URLs, issues, comments, or citations.
- If the retrieved context does not contain enough information to answer,
  set insufficient_context to true.
- If the question contains a false premise that is not supported by the
  retrieved context, do not accept the premise as fact.
- Return an answer, source_ids, and insufficient_context.
- source_ids must refer only to SOURCE numbers present in the retrieved context.
- Do not invent source IDs.
"""

def get_sources_from_db(question: str) -> list[tuple[str, dict]]:
    embed_model = SentenceTransformer(settings.embedding_model_name)
    q_embeddings = embed_model.encode(question, normalize_embeddings=True, show_progress_bar=True)
    chroma_client = chromadb.PersistentClient(path=settings.vector_db_path)
    collection = chroma_client.get_or_create_collection(
        name=settings.collection_name, 
        metadata={"hnsw:space": settings.space_type},
    )

    db_results = collection.query(
        query_embeddings=[q_embeddings],
        n_results=settings.result_limit,
    )

    return list(
                zip(
                    db_results["documents"][0],
                    db_results["metadatas"][0],
                )
            )

def get_llm_answer(question: str, context: str) -> LLMAnswer:
    model = OpenAIChatModel(
        settings.llm_model_name,
        provider=OpenRouterProvider(api_key=settings.llm_api_key.get_secret_value()),
    )

    agent = Agent(
        model,
        output_type=LLMAnswer,
        system_prompt=SYSTEM_PROMPT,
        retries=2,
    )
    
    try:
        result = agent.run_sync(
            f"""
                Question:
                {question}

                Retrieved context:
                {context}
                """
        )
        return result.output
    except UnexpectedModelBehavior as exc:
        raise RuntimeError(f"LLM failed to produce a valid answer after 3 attempts: {exc}") from exc

def ask(question: str) -> AnswerModel:
    if not settings.llm_api_key:
        raise RuntimeError("LLM_API_KEY environment variable not set")

    retrieved_sources = get_sources_from_db(question)

    retrieved_context = []
    for i, (document, metadata) in enumerate(retrieved_sources, start=1,
    ):
        retrieved_context.append(
            f"""
            SOURCE {i}
            Metadata: {metadata}

            Content:
            {document}
            """
        )

    context = "\n\n---\n\n".join(retrieved_context)
    llm_answer = get_llm_answer(question, context)

    if llm_answer.insufficient_context:
        citations = []
    else:
        citations = list(
            dict.fromkeys(
                retrieved_sources[source_id - 1][1]["url"]
                for source_id in llm_answer.source_ids
            )
        )

    return AnswerModel(
        answer=llm_answer.answer,
        citations=citations,
        insufficient_context=llm_answer.insufficient_context,
    )

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("question")
    args = parser.parse_args()

    result = ask(args.question)

    print(f"{result.answer}\n")
    if result.citations:
        print(f"Relevant sources:")
        for source in result.citations:
            print(f"{source}")
    print(f"\ninsufficient_context = {result.insufficient_context}")
    

if __name__ == "__main__":
    main()
