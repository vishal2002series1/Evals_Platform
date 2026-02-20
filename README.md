# Wealth LLM Evaluation Asset — v1.1

This package provides a wealth-domain evaluation dataset, policy rules, SOP clause library, judge prompts, goldens, red-team packs, and a run configuration to execute end-to-end evaluation.

## Contents
- datasets/wealth_queries_v1.json — 100 synthetic client queries with expected behaviour tags
- policies/wealth_policy_rules_v1.yaml — evaluation policy + tag-to-evaluator requirements + hard-fail rules
- sops/wealth_sops_clause_level_v1.yaml — 10 SOPs split into clause-level YAML
- prompts/llm_judge_templates_v1.md — single-response + pairwise judge templates
- goldens/wealth_goldens_v1.json(.jsonl) — good vs bad reference responses for calibration
- redteam/wealth_redteam_pack_v1.yaml — wealth-specific red-team prompt packs
- run_config.yaml — end-to-end run config (paths, models, evaluators, scoring, reporting)

## How to use (high level)
1) Generate model responses for each dataset query.
2) Select SOP snippets based on tags and inject into the LLM-judge prompt.
3) Run evaluators and apply policy hard-fails.
4) Produce report outputs (JSONL/CSV) for analysis and regression tracking.


## Added in v1.2
- selectors/sop_selector_v1.yaml — maps tags to SOP clause IDs
- selectors/sop_clause_lookup_v1.json — clause_id -> clause text/metadata lookup
- runner/run_eval.py — skeleton runner to execute end-to-end evaluation (model calls are stubs)

## Azure OpenAI provider (v1.3)

### Install
- `pip install openai>=1.0.0 pyyaml`

### Set environment variables
- `AZURE_OPENAI_ENDPOINT` = https://<your-resource>.openai.azure.com
- `AZURE_OPENAI_API_KEY` = <key>
- `AZURE_OPENAI_API_VERSION` = your approved API version (example: 2024-02-15-preview)
- `AZURE_OPENAI_DEFAULT_DEPLOYMENT` = your deployment name (example: gpt-4o-mini)

### Configure
Edit `run_config.yaml`:
- `models.candidate_model.provider: azure_openai`
- `models.candidate_model.model_name: <deployment_name>` (or rely on AZURE_OPENAI_DEFAULT_DEPLOYMENT)
- same for `models.judge_model`

### Run
`python runner/run_eval.py --root . --config run_config.yaml --limit 20`

## FastAPI (API Layer)

### Install
pip install -r requirements_api.txt

### Run
uvicorn api.app:app --host 0.0.0.0 --port 8000

## Streamlit (UI Layer)

### Install
pip install -r requirements_ui.txt

### Run
streamlit run ui/streamlit_app.py

## Azure configuration
Copy .env.example to .env and set:
- AZURE_OPENAI_ENDPOINT
- AZURE_OPENAI_API_KEY
- AZURE_OPENAI_API_VERSION
- AZURE_OPENAI_DEFAULT_DEPLOYMENT
