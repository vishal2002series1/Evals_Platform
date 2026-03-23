from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional


class EvaluateRequest(BaseModel):
    # Evaluate a single query or a dataset query_id
    query: Optional[str] = None
    query_id: Optional[int] = None
    expected_tags: Optional[List[str]] = None

    # candidate response can be supplied (skip generation) OR generated using model
    candidate_response: Optional[str] = None

    # run settings
    use_judge: bool = True
    use_rag_context: bool = False
    rag_context: Optional[str] = None

    # optional override of model deployment names
    candidate_model_name: Optional[str] = None
    judge_model_name: Optional[str] = None

    judge_id: Optional[str] = "judge_default_v1"


class EvaluateResponse(BaseModel):
    query_id: Optional[int] = None

    query: str
    expected_tags: List[str]

    sop_clause_ids: List[str]
    sop_snippets: str

    candidate_response: str

    heuristic: Dict[str, Any]

    judge_struct: Dict[str, Any]                     # <-- REQUIRED  
    judge_prompt: Optional[str] = None
    judge_output_raw: Optional[str] = None

    hard_fail: bool                                  # <-- REQUIRED  
    hard_fail_ids: List[str]                         # <-- REQUIRED  

    rai_judgement: Optional[Dict[str, Any]] = None   # <-- Include since you added this

class BatchRunRequest(BaseModel):
    limit: int = Field(default=100, ge=1, le=1000)
    use_judge: bool = True


class BatchRunResponse(BaseModel):
    run_id: str
    results_jsonl: str
    results_csv: str
    count: int


class GoldensResponse(BaseModel):
    version: str
    items: List[Dict[str, Any]]


class RedteamResponse(BaseModel):
    version: str
    packs: List[Dict[str, Any]]


# --- NEW SCHEMAS FOR AUTO-TAGGING ---
class SuggestTagsRequest(BaseModel):
    query: str

class SuggestTagsResponse(BaseModel):
    suggested_tags: List[str]
    matched_query: str
    similarity_score: float