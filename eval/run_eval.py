"""RAGAS evaluation for the RAG pipeline.

Runs against the live app over HTTP (no import of backend code, no dependency overlap
with backend/requirements.txt) - start the stack first, then run this script:

    docker-compose up --build
    cd eval
    pip install -r requirements.txt
    python run_eval.py

Reads DATABASE_URL-adjacent settings from the repo root .env: API_KEY, LLM_PROVIDER,
OPENAI_API_KEY/GOOGLE_API_KEY, and the *_CHAT_MODEL/*_EMBEDDING_MODEL vars, so the judge
model matches whichever provider the app itself is currently configured to use.
"""
import json
import sys
import time
from pathlib import Path

import httpx
from datasets import Dataset
from dotenv import load_dotenv
from ragas import evaluate
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import answer_relevancy, context_precision, context_recall, faithfulness
from ragas.run_config import RunConfig

from qa_dataset import QA_PAIRS

REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(REPO_ROOT / ".env")

import os  # noqa: E402 - after load_dotenv so env vars are populated first

API_BASE_URL = os.environ.get("EVAL_API_URL", "http://localhost:8000")
API_KEY = os.environ["API_KEY"]
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "openai")
SAMPLE_DOCS_DIR = Path(__file__).parent / "sample_docs"
UPLOAD_TIMEOUT_S = 60
RESULTS_PATH = Path(__file__).parent / "results.json"
# Gemini free tier caps at 15 requests/minute; RAGAS's default of 16 concurrent judge-LLM
# calls blows straight through that, so throttle hard when the judge is Gemini. OpenAI
# paid tiers have much higher RPM, so leave RAGAS's default concurrency there.
EVAL_MAX_WORKERS = int(os.environ.get("EVAL_MAX_WORKERS", "1" if LLM_PROVIDER == "gemini" else "16"))

HEADERS = {"X-API-Key": API_KEY}


def upload_documents(client: httpx.Client) -> list[str]:
    doc_ids = []
    for path in sorted(SAMPLE_DOCS_DIR.glob("*.txt")):
        with open(path, "rb") as f:
            resp = client.post(
                f"{API_BASE_URL}/api/v1/documents/upload",
                headers=HEADERS,
                files={"file": (path.name, f, "text/plain")},
            )
        resp.raise_for_status()
        doc_ids.append(resp.json()["id"])
        print(f"  uploaded {path.name} -> {doc_ids[-1]}")
    return doc_ids


def wait_for_ready(client: httpx.Client, doc_id: str) -> None:
    deadline = time.time() + UPLOAD_TIMEOUT_S
    while time.time() < deadline:
        resp = client.get(f"{API_BASE_URL}/api/v1/documents/{doc_id}", headers=HEADERS)
        resp.raise_for_status()
        status = resp.json()["status"]
        if status == "ready":
            return
        if status == "failed":
            raise RuntimeError(f"document {doc_id} failed to ingest")
        time.sleep(1)
    raise TimeoutError(f"document {doc_id} did not become ready within {UPLOAD_TIMEOUT_S}s")


def ask(client: httpx.Client, question: str, document_ids: list[str]) -> tuple[str, list[str]]:
    answer_parts = []
    contexts: list[str] = []
    buffer = ""
    with client.stream(
        "POST",
        f"{API_BASE_URL}/api/v1/query/stream",
        headers=HEADERS,
        json={"question": question, "document_ids": document_ids},
    ) as response:
        response.raise_for_status()
        for chunk in response.iter_text():
            buffer += chunk
            *lines, buffer = buffer.split("\n")
            for line in lines:
                if not line.startswith("data: "):
                    continue
                payload = line[len("data: "):]
                if payload == "[DONE]":
                    return "".join(answer_parts), contexts
                if payload.startswith("[ERROR]"):
                    raise RuntimeError(f"query failed: {payload}")
                if payload.startswith("[SOURCES] "):
                    sources = json.loads(payload[len("[SOURCES] "):])
                    contexts = [s["content"] for s in sources]
                    continue
                answer_parts.append(payload)
    return "".join(answer_parts), contexts


def _patch_gemini_temperature_kwarg(cls):
    """langchain-google-genai==1.0.10 forwards an unrecognized top-level `temperature`
    kwarg straight into the raw SDK's generate_content(), which only accepts a
    `generation_config` dict - raises "unexpected keyword argument 'temperature'".
    ragas always passes a runtime temperature override when calling the judge LLM, so
    this folds it into generation_config instead of leaving it to fall through raw.
    """

    def _generate(self, *args, **kwargs):
        temperature = kwargs.pop("temperature", None)
        if temperature is not None:
            kwargs["generation_config"] = {**(kwargs.get("generation_config") or {}), "temperature": temperature}
        return cls._generate(self, *args, **kwargs)

    async def _agenerate(self, *args, **kwargs):
        temperature = kwargs.pop("temperature", None)
        if temperature is not None:
            kwargs["generation_config"] = {**(kwargs.get("generation_config") or {}), "temperature": temperature}
        return await cls._agenerate(self, *args, **kwargs)

    return type(cls.__name__, (cls,), {"_generate": _generate, "_agenerate": _agenerate})


def build_judge():
    if LLM_PROVIDER == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings

        ChatGoogleGenerativeAI = _patch_gemini_temperature_kwarg(ChatGoogleGenerativeAI)
        llm = ChatGoogleGenerativeAI(
            model=os.environ.get("GEMINI_CHAT_MODEL", "gemini-3.1-flash-lite"),
            google_api_key=os.environ["GOOGLE_API_KEY"],
            temperature=0,
        )
        embeddings = GoogleGenerativeAIEmbeddings(
            model=os.environ.get("GEMINI_EMBEDDING_MODEL", "models/gemini-embedding-001"),
            google_api_key=os.environ["GOOGLE_API_KEY"],
        )
    else:
        from langchain_openai import ChatOpenAI, OpenAIEmbeddings

        llm = ChatOpenAI(
            model=os.environ.get("OPENAI_CHAT_MODEL", "gpt-4o-mini"),
            openai_api_key=os.environ["OPENAI_API_KEY"],
            temperature=0,
        )
        embeddings = OpenAIEmbeddings(
            model=os.environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
            openai_api_key=os.environ["OPENAI_API_KEY"],
        )
    return LangchainLLMWrapper(llm), LangchainEmbeddingsWrapper(embeddings)


def main():
    print(f"Evaluating against {API_BASE_URL} (judge provider: {LLM_PROVIDER})")

    with httpx.Client(timeout=120) as client:
        print("Uploading sample documents...")
        doc_ids = upload_documents(client)
        print("Waiting for ingestion...")
        for doc_id in doc_ids:
            wait_for_ready(client, doc_id)

        print(f"Asking {len(QA_PAIRS)} questions...")
        rows = []
        for i, pair in enumerate(QA_PAIRS, 1):
            answer, contexts = ask(client, pair["question"], doc_ids)
            rows.append(
                {
                    "question": pair["question"],
                    "answer": answer,
                    "contexts": contexts or [""],
                    "ground_truth": pair["ground_truth"],
                }
            )
            print(f"  [{i}/{len(QA_PAIRS)}] {pair['question']}")

        print("Cleaning up uploaded documents...")
        for doc_id in doc_ids:
            client.delete(f"{API_BASE_URL}/api/v1/documents/{doc_id}", headers=HEADERS)

    print(f"Scoring with RAGAS (this makes real LLM calls, max_workers={EVAL_MAX_WORKERS})...")
    judge_llm, judge_embeddings = build_judge()
    dataset = Dataset.from_list(rows)
    result = evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
        llm=judge_llm,
        embeddings=judge_embeddings,
        run_config=RunConfig(max_workers=EVAL_MAX_WORKERS, max_wait=90, max_retries=15),
    )

    df = result.to_pandas()
    RESULTS_PATH.write_text(df.to_json(orient="records", indent=2))
    print(f"\nSaved per-question results to {RESULTS_PATH}\n")
    print("Aggregate scores:")
    for metric in ("faithfulness", "answer_relevancy", "context_precision", "context_recall"):
        print(f"  {metric}: {df[metric].mean():.3f}")


if __name__ == "__main__":
    try:
        main()
    except httpx.ConnectError:
        print(f"Could not reach {API_BASE_URL} - is `docker-compose up` running?", file=sys.stderr)
        sys.exit(1)
