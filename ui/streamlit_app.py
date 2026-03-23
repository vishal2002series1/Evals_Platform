import streamlit as st
import pandas as pd
import requests
import yaml
import json
import sys
from pathlib import Path
import base64
import os

# ================================
#   PROJECT SETUP
# ================================
ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from ui.ui_utils import load_jsonl

# ================================
#   STREAMLIT SETTINGS
# ================================
st.set_page_config(
    page_title="Wealth LLM Evaluation Workbench",
    layout="wide"
)

# ================================
# EY Branding (visual header + sidebar logo)
# ================================
def load_logo_b64():
    logo_file = ROOT / "ui" / "assets" / "ey_logo.png"
    if not logo_file.exists():
        return ""
    with open(logo_file, "rb") as f:
        return base64.b64encode(f.read()).decode()

logo_b64 = load_logo_b64()

if logo_b64:
    st.markdown(
        f"""
        <style>
            .ey-header {{
                background-color: #000;
                padding: 14px 20px;
                border-radius: 6px;
                margin-bottom: 20px;
                display: flex;
                align-items: center;
                justify-content: left;
            }}
            .ey-header img {{
                height: 48px;
            }}
        </style>
        <div class="ey-header">
            <img src="data:image/png;base64,{logo_b64}" alt="EY Logo" />
        </div>
        """,
        unsafe_allow_html=True
    )

    st.sidebar.markdown(
        f"""
        <div style="display:flex;align-items:center;margin-bottom:12px;">
          <img src="data:image/png;base64,{logo_b64}" alt="EY Logo" style="height:34px;" />
        </div>
        """,
        unsafe_allow_html=True
    )

# ================================
#   API HELPERS
# ================================
API = st.sidebar.text_input("API Base URL", value=os.getenv("API_URL", "http://evals-api:8000"))

def api_get(path):
    r = requests.get(f"{API}{path}", timeout=120)
    r.raise_for_status()
    return r.json()

def api_post(path, payload):
    r = requests.post(f"{API}{path}", json=payload, timeout=300)
    r.raise_for_status()
    return r.json()

def get_judge_options():
    """Helper to safely fetch judges from the API"""
    try:
        judges = api_get("/judges")
        return {j["name"]: j["id"] for j in judges}
    except Exception:
        return {"Standard Wealth Compliance Judge (Fallback)": "judge_default_v1"}

# ================================
#   NAVIGATION
# ================================
def go_to_results():
    st.session_state["current_page"] = "Results Explorer"

if "current_page" not in st.session_state:
    st.session_state["current_page"] = "Run Evaluation"

page = st.sidebar.radio(
    "Navigate",
    [
        "Run Evaluation",
        "Evaluate Single",
        "Results Explorer",
        "Judge Studio",
        "Policy & SOP Browser"
    ],
    key="current_page"
)

st.title("Wealth LLM Evaluation Workbench")

# ================================
#   APP PAGES
# ================================

if page == "Run Evaluation":
    st.subheader("Batch Run")
    
    if "run_status_text" not in st.session_state:
        st.session_state["run_status_text"] = ""
    if "run_progress" not in st.session_state:
        st.session_state["run_progress"] = 0.0
    if "run_complete" not in st.session_state:
        st.session_state["run_complete"] = False
    
    col1, col2, col3, col4 = st.columns(4)
    limit = col1.number_input("Number of queries", min_value=1, max_value=1000, value=100, step=10)
    use_judge = col2.checkbox("Use LLM Judge", value=True)
    
    # --- DYNAMIC JUDGE SELECTOR ---
    judge_opts = get_judge_options()
    selected_judge_name = col3.selectbox("Select Evaluator", options=list(judge_opts.keys()), key="batch_judge")
    selected_judge_id = judge_opts[selected_judge_name]
    
    run_btn = col4.button("Run Now", type="primary")

    progress_bar = st.progress(st.session_state["run_progress"])
    status_text = st.empty()
    status_text.text(st.session_state["run_status_text"])
    
    if st.session_state["run_complete"]:
        st.success(f"Run complete: {st.session_state.get('last_run_id', '')}")
        st.write("Artifacts")
        st.code(st.session_state.get('latest_jsonl', ''))
        st.code(st.session_state.get('latest_csv', ''))
        st.button("📊 View Results in Explorer", type="primary", on_click=go_to_results)

    if run_btn:
        import uuid, csv
        st.session_state["run_complete"] = False
        st.session_state["run_progress"] = 0.0
        progress_bar.progress(0.0)
        
        cfg = api_get("/config")
        dataset_path = ROOT / cfg["paths"]["dataset"]
        with open(dataset_path, "r", encoding="utf-8") as f:
            dataset = json.load(f)
            
        queries_to_run = dataset["queries"][:int(limit)]
        total = len(queries_to_run)
        run_id = f"run_{uuid.uuid4().hex[:10]}"
        st.session_state["last_run_id"] = run_id
        
        out_dir = ROOT / "outputs"
        out_dir.mkdir(exist_ok=True)
        jsonl_path = out_dir / f"{run_id}.jsonl"
        csv_path = out_dir / f"{run_id}.csv"
        csv_rows = []
        
        with open(jsonl_path, "w", encoding="utf-8") as jf:
            for i, item in enumerate(queries_to_run):
                msg = f"Evaluating {i+1} of {total}..."
                status_text.text(msg)
                st.session_state["run_status_text"] = msg
                
                # --- SEND JUDGE ID TO API ---
                res = api_post("/evaluate", {
                    "query_id": item["id"], 
                    "use_judge": bool(use_judge),
                    "judge_id": selected_judge_id
                })
                
                record = {"run_id": run_id, "query_id": item["id"], "category": item["category"], **res}
                jf.write(json.dumps(record, ensure_ascii=False) + "\n")
                
                h = res.get("heuristic", {})
                j = res.get("judge_struct", {})
                
                def _as_str(val):
                    if val is None: return ""
                    if isinstance(val, str): return val
                    try: return json.dumps(val, ensure_ascii=False)
                    except: return str(val)
                
                csv_rows.append({
                    "query_id": item["id"],
                    "category": item["category"],
                    "hard_fail": bool(h.get("hard_fail_ids", [])),
                    "hard_fail_ids": ";".join(h.get("hard_fail_ids", [])),
                    "tone_score": (h.get("tone") or {}).get("tone_score", 0),
                    "prediction_flag": bool((h.get("no_prediction") or {}).get("prediction_flags")),
                    "guarantee_flag": (h.get("no_guarantee") or {}).get("count", 0) > 0,
                    "disclaimer_required": ("DISCLAIM" in item["tags"]),
                    "disclaimer_present": (h.get("disclosures") or {}).get("disclaimer_present"),
                    "judge_verdict": j.get("verdict"),
                    "judge_score": j.get("overall_score"),
                    "judge_hard_fail": j.get("hard_fail_triggered"),
                    "judge_output_raw": _as_str(res.get("judge_output_raw")),
                    "judge_prompt": _as_str(res.get("judge_prompt")),
                    "candidate_response": _as_str(res.get("candidate_response")),
                    "sop_snippets": _as_str(res.get("sop_snippets")),
                })
                current_progress = (i + 1) / total
                progress_bar.progress(current_progress)
                st.session_state["run_progress"] = current_progress
                
        with open(csv_path, "w", encoding="utf-8", newline="") as cf:
            writer = csv.DictWriter(cf, fieldnames=list(csv_rows[0].keys()))
            writer.writeheader()
            writer.writerows(csv_rows)
            
        st.session_state["run_status_text"] = "Batch evaluation complete! ✅"
        st.session_state["latest_jsonl"] = f"outputs/{jsonl_path.name}"
        st.session_state["latest_csv"] = f"outputs/{csv_path.name}"
        st.session_state["run_complete"] = True
        st.rerun()

elif page == "Evaluate Single":
    st.subheader("Single Query Evaluation")
    mode = st.radio("Input mode", ["By query text", "By query_id (from dataset)"], horizontal=True)

    judge_opts = get_judge_options()

    if mode == "By query text":
        query = st.text_area("Query", height=90, placeholder="Type a client question...")
        if st.button("✨ Auto-Detect Tags"):
            if query.strip():
                with st.spinner("Finding semantic match..."):
                    res = api_post("/suggest_tags", {"query": query})
                    st.session_state["auto_tags"] = res["suggested_tags"]
            else:
                st.warning("Please enter a query first.")
        
        TAGS = ["EDU_ONLY", "PROCESS_FRAMING", "NO_ADVICE", "REFUSE_SPECIFIC", "DEFER_ADVISOR", "DISCLAIM", "CLARIFY", "NO_PREDICTION", "NO_GUARANTEE", "TONE_NEUTRAL", "EMPATHY", "ESCALATE", "PII_SAFE"]
        if "auto_tags" not in st.session_state: st.session_state["auto_tags"] = ["EDU_ONLY"]

        expected_tags = st.multiselect("Select expected tags", options=TAGS, default=st.session_state["auto_tags"])
        candidate_response = st.text_area("Candidate response (optional)", height=140)

        col1, col2, col3 = st.columns([1, 1, 2])
        use_judge = col1.checkbox("Use LLM Judge", value=True)
        add_rag = col2.checkbox("Provide RAG context", value=False)
        
        # --- DYNAMIC JUDGE SELECTOR ---
        selected_judge_name = col3.selectbox("Select AI Judge", options=list(judge_opts.keys()), key="single_txt_judge")
        selected_judge_id = judge_opts[selected_judge_name]
        
        rag_context = st.text_area("RAG Context", height=120) if add_rag else None

        if st.button("Evaluate", type="primary"):
            payload = {
                "query": query, 
                "expected_tags": expected_tags, 
                "candidate_response": candidate_response if candidate_response.strip() else None, 
                "use_judge": use_judge, 
                "use_rag_context": add_rag, 
                "rag_context": rag_context,
                "judge_id": selected_judge_id # --- PASS JUDGE ID TO API ---
            }
            with st.spinner("Evaluating..."):
                out = api_post("/evaluate", payload)
            st.success("Done")
            st.markdown("### Candidate Response")
            st.write(out["candidate_response"])

            st.markdown("## 🟦 Heuristic Evaluation")
            h = out.get("heuristic", {})
            h_df = pd.DataFrame(list(h.items()), columns=["Metric", "Value"])
            st.table(h_df)

            st.markdown("## 🟩 LLM Judge Evaluation")
            j = out.get("judge_struct", {})
            st.json(j)

    else:
        qid = st.number_input("query_id", min_value=1, value=21)
        
        col1, col2 = st.columns([1, 2])
        use_judge = col1.checkbox("Use LLM Judge", value=True, key="use_judge_id_mode")
        selected_judge_name = col2.selectbox("Select AI Judge", options=list(judge_opts.keys()), key="single_id_judge")
        selected_judge_id = judge_opts[selected_judge_name]
        
        if st.button("Evaluate query_id", type="primary"):
            with st.spinner("Evaluating..."):
                out = api_post("/evaluate", {
                    "query_id": int(qid), 
                    "use_judge": use_judge,
                    "judge_id": selected_judge_id # --- PASS JUDGE ID TO API ---
                })
            st.write("Query:", out["query"])
            st.write("Response:", out["candidate_response"])
            st.json(out["rai_judgement"])

elif page == "Results Explorer":
    st.subheader("Results Explorer")
    jsonl_path = st.text_input("Path to results.jsonl", value=st.session_state.get("latest_jsonl", "outputs/results.jsonl"))
    csv_path = st.text_input("Path to results.csv", value=st.session_state.get("latest_csv", "outputs/results.csv"))

    if st.button("Load Data"):
        st.session_state["df_jsonl"] = load_jsonl(jsonl_path)
        st.session_state["df_csv"] = pd.read_csv(csv_path)

    if "df_csv" in st.session_state:
        st.dataframe(st.session_state["df_csv"])

elif page == "Judge Studio":
    st.subheader("👨‍⚖️ AI Judge Studio")
    st.markdown("Define custom evaluation criteria and metrics for your LLM judges.")

    try:
        judges = api_get("/judges")
    except Exception as e:
        st.error(f"Could not connect to API: {e}")
        judges = []

    col_list, col_editor = st.columns([1, 3])

    with col_list:
        st.markdown("### Your Judges")
        judge_names = [j["name"] for j in judges]
        selected_name = st.radio("Select Judge", ["➕ Create New"] + judge_names)

    current_judge = None
    if selected_name != "➕ Create New":
        current_judge = next(j for j in judges if j["name"] == selected_name)

    with col_editor:
        if selected_name == "➕ Create New":
            st.markdown("### Create New Judge Profile")
            j_id = None
            j_name = st.text_input("Judge Name", placeholder="e.g., Strict Compliance Judge")
            j_desc = st.text_input("Description", placeholder="Primary focus of this judge")
            j_prompt = st.text_area("System Prompt", height=300, value="You are a specialized auditor...")
            existing_metrics = [
                {"name": "verdict", "type": "string", "description": "PASS or FAIL"},
                {"name": "overall_score", "type": "integer", "description": "1-5 quality score"}
            ]
        else:
            st.markdown(f"### Editing Profile: {current_judge['name']}")
            j_id = current_judge["id"]
            j_name = st.text_input("Judge Name", value=current_judge["name"])
            j_desc = st.text_input("Description", value=current_judge["description"])
            j_prompt = st.text_area("System Prompt", height=300, value=current_judge["system_prompt"])
            existing_metrics = current_judge.get("metrics", [])

        st.info("💡 **Variables available:** `{{user_query}}`, `{{assistant_response}}`, `{{sop_snippets_text}}` and `{{policy_rules_text}}`.")

        st.markdown("#### 📊 Evaluation Rubric (Output Metrics)")
        edited_metrics = st.data_editor(
            existing_metrics,
            num_rows="dynamic",
            column_config={
                "name": st.column_config.TextColumn("Metric ID", required=True),
                "type": st.column_config.SelectboxColumn("Type", options=["string", "integer", "boolean"], required=True),
                "description": st.column_config.TextColumn("Guidance for LLM", required=True),
            },
            key="metrics_editor"
        )

        if st.button("💾 Save Judge Profile", type="primary"):
            payload = {
                "id": j_id,
                "name": j_name,
                "description": j_desc,
                "system_prompt": j_prompt,
                "metrics": edited_metrics
            }
            try:
                api_post("/judges", payload)
                st.success("Judge Profile Saved!")
                st.rerun()
            except Exception as e:
                st.error(f"Save failed: {e}")

elif page == "Policy & SOP Browser":
    st.subheader("Policy & SOP Browser")
    cfg = api_get("/config")
    st.code(yaml.safe_dump(cfg, sort_keys=False))