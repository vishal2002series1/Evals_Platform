import os
from fastapi import FastAPI, HTTPException
from dotenv import load_dotenv

# 1. LOAD ENV VARS FIRST BEFORE ANYTHING ELSE!
load_dotenv()

# 2. NOW IMPORT LOCAL MODULES
from api.schemas import (
    EvaluateRequest, EvaluateResponse,
    BatchRunRequest, BatchRunResponse,
    GoldensResponse, RedteamResponse,
    SuggestTagsRequest, SuggestTagsResponse
)
from api.services import evaluate_one, run_batch, get_goldens, get_redteam, suggest_tags
from api.utils import load_yaml

app = FastAPI(title="Wealth LLM Evaluation API", version="1.0")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/config")
def config():
    cfg = load_yaml("run_config.yaml")
    
    # Inject active feature flags into the config payload
    cfg["features"] = {
        "observability_xray": os.getenv("ENABLE_OBSERVABILITY_XRAY", "false").lower() == "true"
    }
    return cfg


@app.post("/evaluate", response_model=EvaluateResponse)
def evaluate(req: EvaluateRequest):
    if not req.query and not req.query_id:
        raise HTTPException(status_code=400, detail="Provide query or query_id")

    query = req.query
    expected_tags = req.expected_tags or []

    # If query_id is provided, fetch from dataset
    if req.query_id and not req.query:
        cfg = load_yaml("run_config.yaml")
        import json
        from pathlib import Path
        dataset = json.loads(Path(cfg["paths"]["dataset"]).read_text(encoding="utf-8"))
        item = next((x for x in dataset["queries"] if x["id"] == req.query_id), None)
        if not item:
            raise HTTPException(status_code=404, detail="query_id not found")
        query = item["query"]
        expected_tags = item["tags"]

    r = evaluate_one(
        query=query,
        expected_tags=expected_tags,
        candidate_response=req.candidate_response,
        use_judge=req.use_judge,
        rag_context=req.rag_context if req.use_rag_context else None,
        candidate_model_override=req.candidate_model_name,
        judge_model_override=req.judge_model_name,
    )

    return {"query_id": req.query_id, **r}


@app.post("/run", response_model=BatchRunResponse)
def run(req: BatchRunRequest):
    r = run_batch(limit=req.limit, use_judge=req.use_judge)
    return r


@app.get("/goldens", response_model=GoldensResponse)
def goldens():
    return get_goldens()


@app.get("/redteam", response_model=RedteamResponse)
def redteam():
    return get_redteam()


# --- NEW ENDPOINT FOR AUTO-TAGGING ---
@app.post("/suggest_tags", response_model=SuggestTagsResponse)
def api_suggest_tags(req: SuggestTagsRequest):
    if not req.query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    return suggest_tags(req.query)