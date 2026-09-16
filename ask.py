import argparse
import chromadb
import os
import json

from openai import OpenAI
from dotenv import load_dotenv
from pydantic import ValidationError
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
- Return ONLY valid JSON with exactly these fields:
    {
      "answer": string,
      "source_ids": [integer, ...],
      "insufficient_context": boolean
    }
- source_ids must refer only to SOURCE numbers present in the retrieved context.
- Do not invent source IDs.
"""

parser = argparse.ArgumentParser()
parser.add_argument("question")
args = parser.parse_args()

model = SentenceTransformer(settings.embedding_model_name)

def get_sources_from_db(question: str) -> str:
    q_embeddings = model.encode(question, normalize_embeddings=True, show_progress_bar=True)
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

def get_llm_answer(context: str) -> LLMAnswer:
    llm_client = OpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key.get_secret_value(),
    )

    validation_error = None

    for attempt in range(3):
        if validation_error:
            retry_instruction = f"""
            Your previous response failed validation.

            Validation error:
            {validation_error}

            Return corrected JSON only.
            """
        else:
            retry_instruction = ""

        response = llm_client.chat.completions.create(
            model=settings.llm_model_name,
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": f"""
                        Question:
                        {args.question}

                        Retrieved context:
                        {context}

                        {retry_instruction}
                        """,
                },
            ],
        )

        raw_output = response.choices[0].message.content

        try:
            data = json.loads(raw_output)
            return LLMAnswer.model_validate(data)

        except (json.JSONDecodeError, ValidationError) as exc:
            validation_error = str(exc)

    raise RuntimeError(
        "LLM failed to produce a valid AnswerModel after 3 attempts"
    )

def ask(question: str) -> AnswerModel:
    load_dotenv()

    if not settings.llm_api_key:
        raise RuntimeError("LLM_API_KEY environment variable not set")

    retrieved_sources = get_sources_from_db(args.question)

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
    llm_answer = get_llm_answer(context)

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
        citations=citations
    )

def main():
    result = ask(args.question)

    print(f"{result.answer}\n")
    if result.citations:
        print(f"Relevant sources:")
        for source in result.citations:
            print(f"{source}")
    

if __name__ == "__main__":
    main()
