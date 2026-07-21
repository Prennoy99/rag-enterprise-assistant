# RAG evaluation (RAGAS)

Scores the running app's retrieval + generation quality using RAGAS: faithfulness, answer relevancy, context precision, and context recall, against two synthetic sample documents ([sample_docs/](sample_docs/)) and 10 question/ground-truth pairs ([qa_dataset.py](qa_dataset.py)).

This talks to the app entirely over its HTTP API — it doesn't import backend code, so its dependencies (a newer `langchain`/`ragas` stack) never conflict with `backend/requirements.txt`'s older pins.

## Run it

```bash
# from the repo root, with the stack already running:
docker-compose up --build

# in a separate terminal:
cd eval
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python run_eval.py
```

It reads `API_KEY`, `LLM_PROVIDER`, and the active provider's key/model settings from the repo root `.env` — the judge LLM matches whichever provider the app itself is configured to use, so this works with either OpenAI or Gemini without any extra setup. Uploaded eval documents are deleted again at the end of the run.

Output: aggregate scores printed to the console, and per-question detail saved to `results.json` (gitignored — it's a debug artifact, not meant to be committed).

## Notes

- Judge LLM calls are real API calls and cost real (if usually tiny) money/quota — 10 questions × 4 metrics is a modest number of requests, but not free.
- `ground_truth` values are short, literal facts pulled directly from the sample docs — this keeps `context_recall` meaningful without needing a separate answer-writing pass.
