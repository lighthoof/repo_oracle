import json

from pathlib import Path

from models import GoldenDataset, TestCase, AnswerModel
from config import settings
from ask import ask, get_sources_from_db

def check_keywords(case: TestCase, answer: AnswerModel) -> tuple[int,int]:
    keywords_found = 0

    for keyword in case.expected_keywords:
        if keyword.lower() in answer.answer.lower():
            keywords_found += 1
    
    return keywords_found, len(case.expected_keywords)

def check_answer(case: TestCase, answer: AnswerModel) -> bool:
    if case.insufficient_context:
        return answer.insufficient_context

    if answer.insufficient_context:
        return False

    found, expected = check_keywords(case, answer)

    return found == expected

def check_retrieval(case: TestCase, retrieved_sources) -> bool | None:
    if not case.expected_citations:
        return None

    retrieved_urls = {
        metadata["url"]
        for _, metadata in retrieved_sources
    }

    return any(url in retrieved_urls for url in case.expected_citations)

def main() -> None:
    path = settings.testcase_path
    raw_cases = json.loads(path.read_text(encoding="utf-8"))
    validated_cases = GoldenDataset.model_validate(raw_cases)

    retrieval_results = []
    answer_results = []

    for case in validated_cases.test_cases:
        retrieved_sources = get_sources_from_db(case.query)
        answer = None
        try:
            answer = ask(case.query, retrieved_sources)
            answer_correct = check_answer(case, answer)
        except RuntimeError as exc:
            print(f"  LLM error: {exc}")
            answer_correct = False
        
        retrieval_hit = check_retrieval(case, retrieved_sources)
        if retrieval_hit is not None:
            retrieval_results.append(retrieval_hit)

        answer_results.append(answer_correct)

        print(f"\nQuestion: {case.query}")
        print(f"  Retrieval hit: {retrieval_hit}")
        print(f"  Answer correct: {answer_correct}")
        if answer is not None:
            print(f"  insufficient_context: {answer.insufficient_context}")
        else:
            print("  insufficient_context: unavailable (LLM failed)")

        if retrieval_hit is False:
            print("  Expected:", case.expected_citations)
            print("  Retrieved:")
            for _, metadata in retrieved_sources:
                print(f"    {metadata['url']}")

    if retrieval_results:
        retrieval_correct = sum(retrieval_results)
        print(
            f"Retrieval accuracy: "
            f"{retrieval_correct}/{len(retrieval_results)} "
            f"({retrieval_correct / len(retrieval_results):.1%})"
        )
    else:
        print("Retrieval accuracy: N/A")
    answer_correct = sum(answer_results)

    print(
       f"Answer accuracy: "
       f"{answer_correct}/{len(answer_results)} "
       f"({answer_correct / len(answer_results):.1%})"
    )

if __name__ == "__main__":
     main()