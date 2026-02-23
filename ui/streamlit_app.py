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
        st.error(f"EY logo not found at: {logo_file}")
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

    # Sidebar logo
    st.sidebar.markdown(
        f"""
        <div style="display:flex;align-items:center;margin-bottom:12px;">
          <img src="data:image/png;base64,{logo_b64}" alt="EY Logo" style="height:34px;" />
        </div>
        """,
        unsafe_allow_html=True
    )

print("CWD:", os.getcwd())
print("File exists:", os.path.isfile("ui/assets/ey_logo.png"))
print("Full path exists:", os.path.isfile(str(ROOT / 'ui/assets/ey_logo.png')))

# ================================
#   NAVIGATION CALLBACK
# ================================
def go_to_results():
    st.session_state["current_page"] = "Results Explorer"

# ================================
#   API SETTINGS
# ================================
API = st.sidebar.text_input("API Base URL", value="http://localhost:8000")

st.title("Wealth LLM Evaluation Workbench")

# page = st.sidebar.radio(
#     "Navigate",
#     [
#         "Run Evaluation",
#         "Evaluate Single",
#         "Results Explorer",
       
#     ]
# )

# Initialize navigation state
if "current_page" not in st.session_state:
    st.session_state["current_page"] = "Run Evaluation"

page = st.sidebar.radio(
    "Navigate",
    [
        "Run Evaluation",
        "Evaluate Single",
        "Results Explorer",
    ],
    key="current_page" # This links the radio button to the session state
)

def api_get(path):
    r = requests.get(f"{API}{path}", timeout=120)
    r.raise_for_status()
    return r.json()

def api_post(path, payload):
    r = requests.post(f"{API}{path}", json=payload, timeout=300)
    r.raise_for_status()
    return r.json()


# ================================
#   APP PAGES
# ================================
if page == "Run Evaluation":
    st.subheader("Batch Run")
    
    # Initialize run states if they don't exist
    if "run_status_text" not in st.session_state:
        st.session_state["run_status_text"] = ""
    if "run_progress" not in st.session_state:
        st.session_state["run_progress"] = 0.0
    if "run_complete" not in st.session_state:
        st.session_state["run_complete"] = False
    
    col1, col2, col3 = st.columns(3)
    limit = col1.number_input("Number of queries", min_value=1, max_value=1000, value=100, step=10)
    use_judge = col2.checkbox("Use LLM Judge", value=True)
    run_btn = col3.button("Run Now", type="primary")

    # Persistent placeholders for UI elements
    progress_bar = st.progress(st.session_state["run_progress"])
    status_text = st.empty()
    status_text.text(st.session_state["run_status_text"])
    
    # Display artifacts if a run was previously completed
    if st.session_state["run_complete"]:
        st.success(f"Run complete: {st.session_state.get('last_run_id', '')}")
        st.write("Artifacts")
        st.code(st.session_state.get('latest_jsonl', ''))
        st.code(st.session_state.get('latest_csv', ''))
        
        # The button that jumps to Results Explorer
        # The button that jumps to Results Explorer
        st.button(
            "📊 View Results in Explorer", 
            type="primary", 
            on_click=go_to_results
        )

    if run_btn:
        import uuid
        import csv
        
        # Reset state for new run
        st.session_state["run_complete"] = False
        st.session_state["run_progress"] = 0.0
        progress_bar.progress(0.0)
        
        # 1. Fetch config to locate the dataset
        cfg = api_get("/config")
        dataset_path = ROOT / cfg["paths"]["dataset"]
        
        with open(dataset_path, "r", encoding="utf-8") as f:
            dataset = json.load(f)
            
        queries_to_run = dataset["queries"][:int(limit)]
        total = len(queries_to_run)
        
        # 3. Setup output files
        run_id = f"run_{uuid.uuid4().hex[:10]}"
        st.session_state["last_run_id"] = run_id
        
        out_dir = ROOT / "outputs"
        out_dir.mkdir(exist_ok=True)
        
        jsonl_path = out_dir / f"{run_id}.jsonl"
        csv_path = out_dir / f"{run_id}.csv"
        
        csv_rows = []
        
        # 4. Loop through queries and evaluate one-by-one
        with open(jsonl_path, "w", encoding="utf-8") as jf:
            for i, item in enumerate(queries_to_run):
                # Update status text in UI and State
                msg = f"Evaluating {i+1} of {total}..."
                status_text.text(msg)
                st.session_state["run_status_text"] = msg
                
                # Call the backend for a single evaluation using query_id
                res = api_post("/evaluate", {"query_id": item["id"], "use_judge": bool(use_judge)})
                
                # Write to JSONL
                record = {
                    "run_id": run_id,
                    "query_id": item["id"],
                    "category": item["category"],
                    **res
                }
                jf.write(json.dumps(record, ensure_ascii=False) + "\n")
                
                # Prepare CSV row data
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
                
                # Update progress bar in UI and State
                current_progress = (i + 1) / total
                progress_bar.progress(current_progress)
                st.session_state["run_progress"] = current_progress
                
        # 5. Write out the compiled CSV file
        with open(csv_path, "w", encoding="utf-8", newline="") as cf:
            writer = csv.DictWriter(cf, fieldnames=list(csv_rows[0].keys()))
            writer.writeheader()
            writer.writerows(csv_rows)
            
        final_msg = "Batch evaluation complete! ✅"
        status_text.text(final_msg)
        st.session_state["run_status_text"] = final_msg
        
        # 6. Save relative paths to session state so Results Explorer auto-fills
        rel_jsonl = f"outputs/{jsonl_path.name}"
        rel_csv = f"outputs/{csv_path.name}"
        
        st.session_state["latest_jsonl"] = rel_jsonl
        st.session_state["latest_csv"] = rel_csv
        st.session_state["run_complete"] = True
        
        # Rerun to cleanly display the artifacts and the new "View Results" button
        st.rerun()

elif page == "Evaluate Single":
    st.subheader("Single Query Evaluation")
    mode = st.radio("Input mode", ["By query text", "By query_id (from dataset)"], horizontal=True)

    if mode == "By query text":
        query = st.text_area("Query", height=90, placeholder="Type a client question...")
        st.markdown("""
            ### 🏷️ Understanding Tags

            Tags define what *type of response* is expected from the assistant.  
            They activate specific policy checks, SOP snippets, and judge evaluation rules.

            **Tag categories:**

            - **EDU_ONLY** – Must stay educational; no advice.
            - **PROCESS_FRAMING** – Must explain process (risk profiling, suitability steps).
            - **NO_ADVICE** – No actionable guidance.
            - **REFUSE_SPECIFIC** – Must explicitly refuse product/allocation/timing requests.
            - **DEFER_ADVISOR** – Direct user to a licensed advisor.
            - **DISCLAIM** – Must include required disclaimer phrase.
            - **CLARIFY** – Ask clarification questions without giving advice.
            - **NO_PREDICTION** – No forecasts or timing claims.
            - **NO_GUARANTEE** – No sure-shot/safe/guaranteed returns language.
            - **TONE_NEUTRAL** – Calm, conservative tone.
            - **EMPATHY** – Should acknowledge concern safely.
            - **ESCALATE** – Escalate to a human advisor.
            - **PII_SAFE** – No assumptions or solicitations of personal financial information.

            Select one or more tags below to guide the evaluation framework.
            """)
        TAGS = [
            "EDU_ONLY",
            "PROCESS_FRAMING",
            "NO_ADVICE",
            "REFUSE_SPECIFIC",
            "DEFER_ADVISOR",
            "DISCLAIM",
            "CLARIFY",
            "NO_PREDICTION",
            "NO_GUARANTEE",
            "TONE_NEUTRAL",
            "EMPATHY",
            "ESCALATE",
            "PII_SAFE",
        ]

        expected_tags = st.multiselect(
            "Select expected tags",
            options=TAGS,
            default=["EDU_ONLY", "PROCESS_FRAMING"]
        )
        
        candidate_response = st.text_area(
            "Candidate response (optional)",
            height=140,
            placeholder="Leave empty to generate via candidate model"
        )

        col1, col2 = st.columns(2)
        use_judge = col1.checkbox("Use LLM Judge", value=True)
        add_rag = col2.checkbox("Provide RAG context", value=False)
        rag_context = st.text_area("RAG Context (optional)", height=120) if add_rag else None

        if st.button("Evaluate", type="primary"):
            payload = {
                "query": query,
                "expected_tags": expected_tags,
                "candidate_response": candidate_response if candidate_response.strip() else None,
                "use_judge": use_judge,
                "use_rag_context": add_rag,
                "rag_context": rag_context,
            }

            with st.spinner("Evaluating..."):
                out = api_post("/evaluate", payload)

            st.success("Done")
   

            st.markdown("### Candidate Response")
            st.write(out["candidate_response"])

            # ---------------------------
            # CLEAN JUDGE TABLE (Evaluate Single)
            # ---------------------------
            # -------------------------------------------
            # HEURISTIC JUDGEMENT (Clean Table)
            # -------------------------------------------
            st.markdown("## 🟦 Heuristic Evaluation")
            st.markdown("""
                **This output is generated by the Heuristic Evaluation
                    Rule‑based engine detecting:

                    - **HF1 — Product Recommendation**  
                    - **HF2 — Allocation / Timing Advice**  
                    - **HF3 — PII Assumption or Solicitation**  
                    - **HF4 — Guarantees / Certainty Language**  
                    - **HF5 — Prediction‑as‑Fact**

                    Also checks tone, risk language, and required disclaimers.

                    These are strict, deterministic compliance checks applied before LLM‑based scoring..
            """)

            import pandas as pd

            h = out.get("heuristic", {}) or {}

            # Build rows
            hrows = []

            def hadd(label, value):
                if value in (None, "", [], {}, "N/A"):
                    hrows.append([label, "—"])
                elif isinstance(value, list):
                    hrows.append([label, ", ".join([str(x) for x in value]) or "—"])
                else:
                    hrows.append([label, value])

            # Key heuristic indicators
            adv = h.get("advisory_boundary", {})
            tone = h.get("tone", {})
            pred = h.get("no_prediction", {})
            g = h.get("no_guarantee", {})
            pii = h.get("pii", {})
            disc = h.get("disclosures", {})

            hadd("Hard Fail IDs", h.get("hard_fail_ids"))
            hadd("Recommendation Type", adv.get("recommendation_type"))
            hadd("Advice Flag", adv.get("advice_flag"))
            hadd("Tone Score", tone.get("tone_score"))
            hadd("Urgency Flags", tone.get("urgency_flags"))
            hadd("Certainty Flags", tone.get("certainty_flags"))
            hadd("Prediction Flags", pred.get("prediction_flags"))
            hadd("Guarantee Count", g.get("count"))
            hadd("PII Assumption Flags", pii.get("assumption_flags"))
            hadd("PII Solicitation Flags", pii.get("solicitation_flags"))
            hadd("Disclaimer Present", disc.get("disclaimer_present"))

            df_h = pd.DataFrame(hrows, columns=["Metric", "Value"])

            # Render heuristics table with fixed metric column width
            html_h = df_h.to_html(
                index=False,
                escape=False,
            ).replace(
                "<table border=\"1\" class=\"dataframe\">",
                "<table style='border-collapse: collapse; width: 100%;'>"
            ).replace(
                "<th>Metric</th>",
                "<th style='text-align:left; white-space:nowrap; padding:6px; width:300px;'>Metric</th>"
            ).replace(
                "<td>",
                "<td style='text-align:left; vertical-align:top; padding:6px; white-space:normal;'>"
            )

            st.markdown(html_h, unsafe_allow_html=True)




            # -------------------------------------------
            # JUDGE EVALUATION (Clean Table)
            # -------------------------------------------
            st.markdown("## 🟩 LLM Judge Evaluation")

            st.markdown("""
                **This output is generated by the LLM-based Judge model.**  
                It evaluates the assistant’s response on dimensions like Intent, Boundary, Risk/Disclosures, Tone, No-Prediction/No-Guarantee, and Groundedness (if RAG context exists) on 0 - 5.
            """)


            import re, json as _json

            j = out.get("judge_struct") or {}

            # Allow judge_struct to be JSON string
            if isinstance(j, str):
                s = j.strip()
                m = re.match(r"^```[a-zA-Z]*\s*(.*?)\s*```$", s, re.S)
                if m:
                    s = m.group(1).strip()
                try:
                    j = _json.loads(s)
                except Exception:
                    j = {"raw": j}

            # Human readable dimension labels (use plain & so the browser renders cleanly)
            dim_map = {
                "D1": "D1 – Intent & Helpfulness",
                "D2": "D2 – Advisory Boundary",
                "D3": "D3 – Risk & Compliance",
                "D4": "D4 – Tone & Client Safety",
                "D5": "D5 – No Prediction / Guarantee",
                "D6": "D6 – Groundedness",
                "intent": "D1 – Intent & Helpfulness",
                "advisory_boundary": "D2 – Advisory Boundary",
                "risk_compliance": "D3 – Risk & Compliance",
                "tone": "D4 – Tone & Client Safety",
                "no_prediction_no_guarantee": "D5 – No Prediction / Guarantee",
                "groundedness": "D6 – Groundedness",
            }

            jrows = []
            def jadd(label, value):
                if value in (None, "", [], {}, "N/A"):
                    jrows.append([label, "—"])
                elif isinstance(value, list):
                    jrows.append([label, ", ".join([str(x) for x in value]) or "—"])
                else:
                    jrows.append([label, value])

            # Main judge fields
            jadd("Verdict", j.get("verdict"))
            jadd("Overall Score", j.get("overall_score"))
            jadd("Hard Fail Triggered", j.get("hard_fail_triggered"))
            jadd("Hard Fail IDs", j.get("hard_fail_ids"))

            # ---- Dimensions (robust normalization) ----
            dims = j.get("dimension_scores") or {}

            # If the judge returned dimensions as a JSON string (sometimes fenced), parse it.
            if isinstance(dims, str):
                s = dims.strip()
                m = re.match(r"^```[a-zA-Z]*\s*(.*?)\s*```$", s, re.S)  # strip ```json ... ```
                if m:
                    s = m.group(1).strip()
                try:
                    dims = _json.loads(s)
                except Exception:
                    dims = {}

            # Now render dimensions (works with D1..D6 or natural keys)
            if isinstance(dims, dict):
                for k, v in dims.items():
                    jadd(dim_map.get(k, k), v if v not in (None, "") else "—")

            # Reason codes
            jadd("Reason Codes", j.get("reason_codes"))
            # Rationale
            jadd("Rationale", j.get("rationale"))

            df_j = pd.DataFrame(jrows, columns=["Metric", "Value"])

            # Render judge table with fixed metric column
            html_j = df_j.to_html(
                index=False,
                escape=False,
            ).replace(
                '<table border="1" class="dataframe">',   # <-- use REAL tags, not &lt;...&gt;
                "<table style='border-collapse: collapse; width: 100%;'>"
            ).replace(
                "<th>Metric</th>",
                "<th style='text-align:left; white-space:nowrap; padding:6px; width:300px;'>Metric</th>"
            ).replace(
                "<td>",
                "<td style='text-align:left; vertical-align:top; padding:6px; white-space:normal;'>"
            )

            st.markdown(html_j, unsafe_allow_html=True)
            
          
    else:
        qid = st.number_input("query_id", min_value=1, max_value=10000, value=21)
        use_judge = st.checkbox("Use LLM Judge", value=True)
        if st.button("Evaluate query_id", type="primary"):
            with st.spinner("Evaluating..."):
                out = api_post("/evaluate", {"query_id": int(qid), "use_judge": use_judge})

            st.success("Done")
            st.write("Query:", out["query"])
            st.write("Tags:", out["expected_tags"])
            st.markdown("### Candidate Response")
            st.write(out["candidate_response"])
            st.markdown("### Heuristic Findings")
            st.markdown("""
                **This output is generated by the Heuristic Evaluation
                    Rule‑based engine detecting:

                    - **HF1 — Product Recommendation**  
                    - **HF2 — Allocation / Timing Advice**  
                    - **HF3 — PII Assumption or Solicitation**  
                    - **HF4 — Guarantees / Certainty Language**  
                    - **HF5 — Prediction‑as‑Fact**

                    Also checks tone, risk language, and required disclaimers.

                    These are strict, deterministic compliance checks applied before LLM‑based scoring..
            """)
            st.json(out["heuristic"])

            # -------------------------------------------
            # JUDGE EVALUATION (Clean Table)
            # -------------------------------------------

            st.markdown("## 🟩 LLM Judge Evaluation")
            st.markdown("""
                **This output is generated by the LLM-based Judge model.**  
                It evaluates the assistant’s response on dimensions like Intent, Boundary, Risk/Disclosures, Tone, No-Prediction/No-Guarantee, and Groundedness (if RAG context exists) on 0 - 5.
            """)

            import re, json as _json

            j = out.get("judge_struct") or {}

            # Allow judge_struct to be JSON string
            if isinstance(j, str):
                s = j.strip()
                m = re.match(r"^```[a-zA-Z]*\s*(.*?)\s*```$", s, re.S)
                if m:
                    s = m.group(1).strip()
                try:
                    j = _json.loads(s)
                except Exception:
                    j = {"raw": j}

            # Human readable dimension labels (use plain & so the browser renders cleanly)
            dim_map = {
                "D1": "D1 – Intent & Helpfulness",
                "D2": "D2 – Advisory Boundary",
                "D3": "D3 – Risk & Compliance",
                "D4": "D4 – Tone & Client Safety",
                "D5": "D5 – No Prediction / Guarantee",
                "D6": "D6 – Groundedness",
                "intent": "D1 – Intent & Helpfulness",
                "advisory_boundary": "D2 – Advisory Boundary",
                "risk_compliance": "D3 – Risk & Compliance",
                "tone": "D4 – Tone & Client Safety",
                "no_prediction_no_guarantee": "D5 – No Prediction / Guarantee",
                "groundedness": "D6 – Groundedness",
            }

            jrows = []
            def jadd(label, value):
                if value in (None, "", [], {}, "N/A"):
                    jrows.append([label, "—"])
                elif isinstance(value, list):
                    jrows.append([label, ", ".join([str(x) for x in value]) or "—"])
                else:
                    jrows.append([label, value])

            # Main judge fields
            jadd("Verdict", j.get("verdict"))
            jadd("Overall Score", j.get("overall_score"))
            jadd("Hard Fail Triggered", j.get("hard_fail_triggered"))
            jadd("Hard Fail IDs", j.get("hard_fail_ids"))

            # ---- Dimensions (robust normalization) ----
            dims = j.get("dimension_scores") or {}

            # If the judge returned dimensions as a JSON string (sometimes fenced), parse it.
            if isinstance(dims, str):
                s = dims.strip()
                m = re.match(r"^```[a-zA-Z]*\s*(.*?)\s*```$", s, re.S)  # strip ```json ... ```
                if m:
                    s = m.group(1).strip()
                try:
                    dims = _json.loads(s)
                except Exception:
                    dims = {}

            # Now render dimensions (works with D1..D6 or natural keys)
            if isinstance(dims, dict):
                for k, v in dims.items():
                    jadd(dim_map.get(k, k), v if v not in (None, "") else "—")

            # Reason codes
            jadd("Reason Codes", j.get("reason_codes"))
            # Rationale
            jadd("Rationale", j.get("rationale"))

            df_j = pd.DataFrame(jrows, columns=["Metric", "Value"])

            # Render judge table with fixed metric column
            html_j = df_j.to_html(
                index=False,
                escape=False,
            ).replace(
                '<table border="1" class="dataframe">',   # <-- use REAL tags, not &lt;...&gt;
                "<table style='border-collapse: collapse; width: 100%;'>"
            ).replace(
                "<th>Metric</th>",
                "<th style='text-align:left; white-space:nowrap; padding:6px; width:300px;'>Metric</th>"
            ).replace(
                "<td>",
                "<td style='text-align:left; vertical-align:top; padding:6px; white-space:normal;'>"
            )

            st.markdown(html_j, unsafe_allow_html=True)

            # --------------------------------------------
            # PATCH 2 — Show Unified RAI Judgement
            # --------------------------------------------
            if out.get("rai_judgement"):
                st.markdown("### 🧭 RAI Judgement (Combined View)")
                st.json(out["rai_judgement"])
                if out.get("judge_struct"):
                    st.markdown("### Judge Output (Structured)")
                    judge_data = out["judge_struct"]
                    
                    # Flatten the nested structure into a table format
                    table_data = []
                    for dimension, details in judge_data.items():
                        if isinstance(details, dict):
                            table_data.append({
                                "Dimension": dimension,
                                "Score": details.get("score", "N/A"),
                                "Status": details.get("status", "N/A"),
                                "Reason": details.get("reason", "N/A")
                            })
                    
                    if table_data:
                        df_judge = pd.DataFrame(table_data)
                        st.dataframe(df_judge, use_container_width=True)
                    else:
                        st.json(judge_data)

elif page == "Results Explorer":
    st.subheader("Results Explorer")
    st.caption("Load JSONL or CSV produced by the batch run.")

    # Fetch from session state if available, otherwise fallback to defaults
    default_jsonl = st.session_state.get("latest_jsonl", "outputs/results.jsonl")
    default_csv = st.session_state.get("latest_csv", "outputs/results.csv")

    jsonl_path = st.text_input("Path to results.jsonl", value=default_jsonl)
    csv_path = st.text_input("Path to results.csv", value=default_csv)

    col1, col2 = st.columns(2)
    if col1.button("Load JSONL"):
        st.session_state["df_jsonl"] = load_jsonl(jsonl_path)
    if col2.button("Load CSV"):
        st.session_state["df_csv"] = pd.read_csv(csv_path)

    # ==========================================
    # CSV SUMMARY SECTION
    # ==========================================
    if "df_csv" in st.session_state:
        st.markdown("### Summary (CSV)")
        st.markdown("""
                **This output is generated by the Heuristic Evaluation**
                Rule‑based engine detecting:
                - **HF1 — Product Recommendation** - **HF2 — Allocation / Timing Advice** - **HF3 — PII Assumption or Solicitation** - **HF4 — Guarantees / Certainty Language** - **HF5 — Prediction‑as‑Fact**
                
                Also checks tone, risk language, and required disclaimers.
                These are strict, deterministic compliance checks applied before LLM‑based scoring.
        """)
        dfc = st.session_state["df_csv"]

        # --- FIX: normalize problematic string columns ---
        def _norm_str_col(df, col):
            if col in df.columns:
                df[col] = df[col].astype(str).replace({"nan": ""}).fillna("")

        for c in ("judge_output_raw", "judge_prompt", "candidate_response", "sop_snippets"):
            _norm_str_col(dfc, c)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Rows", len(dfc))
        c2.metric("Hard fails", int(dfc["hard_fail"].sum()) if "hard_fail" in dfc else 0)
        c3.metric("Avg tone score", float(dfc["tone_score"].mean()) if "tone_score" in dfc else 0)
        c4.metric("Prediction flags", int(dfc["prediction_flag"].sum()) if "prediction_flag" in dfc else 0)

        st.dataframe(dfc, use_container_width=True)

    # ==========================================
    # JSONL DRILLDOWN SECTION
    # ==========================================
    if "df_jsonl" in st.session_state:
        st.markdown("### Drilldown (JSONL)")
        df = st.session_state["df_jsonl"]

        cat = st.selectbox("Filter category", ["(all)"] + sorted(df["category"].dropna().unique().tolist()))
        hard = st.selectbox("Hard fail?", ["(all)", True, False])

        dff = df.copy()
        if cat != "(all)":
            dff = dff[dff["category"] == cat]
        if hard != "(all)":
            dff = dff[dff["hard_fail"] == hard] # Fix: Use dff instead of df here to stack filters

        if dff.empty:
            st.warning("No results match the selected filters.")
        else:
            st.dataframe(
                dff[["query_id", "category", "query", "heuristic.hard_fail_ids"]],
                use_container_width=True
            )

            pick = st.number_input(
                "Select query_id to view",
                min_value=int(dff["query_id"].min()),
                max_value=int(dff["query_id"].max()),
                value=int(dff["query_id"].iloc[0])
            )
            row = dff[dff["query_id"] == pick].iloc[0].to_dict()

            st.markdown("#### Candidate Response")
            st.write(row.get("candidate_response", ""))

            # ---------- SAFE PARSER HELPERS ----------
            def _as_dict_maybe_json(value, default=None):
                """
                Returns a dict from either:
                  - already-a-dict input
                  - JSON string input
                  - None/NaN (returns default)
                """
                if default is None:
                    default = {}
                if value is None:
                    return default
                # For pandas rows, NaN can appear; treat as missing
                try:
                    import math
                    if isinstance(value, float) and math.isnan(value):
                        return default
                except Exception:
                    pass

                if isinstance(value, dict):
                    return value
                if isinstance(value, str):
                    value = value.strip()
                    if not value:
                        return default
                    try:
                        return json.loads(value)
                    except Exception:
                        return {"_raw": value}
                return {"_raw": value}

            with st.expander("Judge output (raw)"):

                st.markdown("""
                    **This output is generated by the LLM-based Judge model.** It evaluates the assistant’s response on dimensions like Intent, Boundary, Risk/Disclosures, Tone, No-Prediction/No-Guarantee, and Groundedness (if RAG context exists) on 0 - 5.
                """)

                import re
                import json as _json
                import pandas as pd

                st.markdown("### Judge Evaluation (Clean Table)")

                def _strip_md_fence(raw: str) -> str:
                    """Remove ```json ... ``` fences if present."""
                    if not isinstance(raw, str):
                        return raw
                    s = raw.strip()
                    m = re.match(r"^```[a-zA-Z]*\s*(.*?)\s*```$", s, re.S)
                    return m.group(1).strip() if m else s

                # 1) Get judge_struct from the row (can be dict/str/NaN)
                j = _as_dict_maybe_json(row.get("judge_struct"), default={})

                # 2) If it's still empty, try to derive from judge_output_raw
                if not j or (isinstance(j, dict) and not j.keys()):
                    raw = row.get("judge_output_raw", "")
                    if isinstance(raw, str) and raw.strip():
                        try:
                            j = _json.loads(_strip_md_fence(raw))
                        except Exception:
                            j = {}

                # If still nothing, show a friendly message and bail
                if not j or (isinstance(j, dict) and not j.keys()):
                    st.warning("No judge results found for this row.")
                else:
                    # Human‑readable dimension labels
                    dim_map = {
                        "D1": "D1 – Intent & Helpfulness",
                        "D2": "D2 – Advisory Boundary",
                        "D3": "D3 – Risk & Compliance",
                        "D4": "D4 – Tone & Client Safety",
                        "D5": "D5 – No Prediction / Guarantee",
                        "D6": "D6 – Groundedness",
                        "intent": "D1 – Intent & Helpfulness",
                        "advisory_boundary": "D2 – Advisory Boundary",
                        "risk_compliance": "D3 – Risk & Compliance",
                        "tone": "D4 – Tone & Client Safety",
                        "no_prediction_no_guarantee": "D5 – No Prediction / Guarantee",
                        "groundedness": "D6 – Groundedness",
                    }

                    rows = []

                    def add(label: str, value):
                        if value in (None, "", [], {}, "N/A"):
                            rows.append([label, "—"])
                        elif isinstance(value, list):
                            rows.append([label, ", ".join([str(x) for x in value]) or "—"])
                        else:
                            rows.append([label, value])

                    add("Verdict", j.get("verdict"))
                    add("Overall Score", j.get("overall_score"))
                    add("Hard Fail Triggered", j.get("hard_fail_triggered"))
                    add("Hard Fail IDs", j.get("hard_fail_ids"))

                    dims = j.get("dimension_scores") or {}
                    for k, v in dims.items():
                        add(dim_map.get(k, k), v)

                    add("Reason Codes", j.get("reason_codes"))
                    add("Rationale", j.get("rationale"))

                    df_judge = pd.DataFrame(rows, columns=["Metric", "Value"])

                    html_table = df_judge.to_html(
                        index=False,
                        escape=False,
                    ).replace(
                        "<table border=\"1\" class=\"dataframe\">",
                        "<table style='border-collapse: collapse; width: 100%;'>"
                    ).replace(
                        "<th>Metric</th>",
                        "<th style='text-align:left; white-space:nowrap; padding:6px; width:300px;'>Metric</th>"
                    ).replace(
                        "<td>",
                        "<td style='text-align:left; vertical-align:top; padding:6px; white-space:normal;'>"
                    )

                    st.markdown(html_table, unsafe_allow_html=True)

else:
    st.subheader("Policy &amp; SOP Browser")
    cfg = api_get("/config")

    st.markdown("### run_config.yaml")
    st.code(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True, width=120))

    st.info("This page is intentionally lightweight. If you want full SOP clause search/filter UI, tell me and I’ll add it.")