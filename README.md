# Airport Operations AI Copilot

An agentic AI copilot for airport ground operations that combines **RAG-based policy intelligence, real-time airport telemetry, multi-agent reasoning, operational tools, guardrails, and human-in-the-loop approval**.

The system is designed for airport operations teams managing driver activity, queues, ETAs, completion rates, cancellations, and surge-related decisions across **SFO, LAX, and JFK**.

---

## 1. Project Overview

Airport operations teams need to make decisions using two types of information:

1. **Operational data** — current airport metrics such as queue size, active drivers, ETA, completion rate, cancellations, and surge multiplier.
2. **Airport policies** — operational, pricing, driver, approval, and compliance rules.

The Airport Operations AI Copilot brings these together into a single conversational interface.

A user can ask questions such as:

* `SFO queue is high. What should we do?`
* `What is the maximum surge multiplier at SFO?`
* `Increase SFO surge to 1.4x`
* `Increase SFO surge to 2.0x`
* `What are the current metrics at LAX?`

The copilot determines the relevant airport, retrieves applicable policies, analyzes operational metrics, evaluates risk, and determines whether an operational action can be executed directly or requires human approval.

---

## 2. Key Features

### Policy RAG

* Airport policies stored as Markdown documents
* Semantic section-based document chunking
* Gemini embeddings using `gemini-embedding-001`
* FAISS vector database for similarity search
* Policy-grounded answers
* Source document and section tracking

### Airport Telemetry

Synthetic airport telemetry contains:

* Queue size
* Active drivers
* Request volume
* Completion rate
* Driver cancellation rate
* Average ETA
* Surge multiplier
* Timestamp

Supported airports:

* SFO — San Francisco International Airport
* LAX — Los Angeles International Airport
* JFK — John F. Kennedy International Airport

### Operational Tools

The copilot can use tools for:

* Retrieving airport metrics
* Calculating driver incentives
* Triggering surge overrides

### Multi-Agent Architecture

The system contains specialized agents:

* **Orchestrator** — coordinates the overall workflow
* **Operations Investigator** — analyzes operational metrics
* **Policy & Compliance** — retrieves and interprets policies
* **Resolution Agent** — determines the appropriate operational response

### Guardrails

The system includes:

* Input validation
* Airport validation
* Risk classification
* Action validation
* Policy validation
* Maximum surge validation
* Human approval workflow
* Audit trail generation

### Human-in-the-Loop

High-risk operational actions require explicit human approval.

For example:

```text
Increase SFO surge to 1.4x
```

The system identifies that the requested action exceeds the SFO approval threshold and places the action into a pending approval state.

The user can then approve or reject the action through the Streamlit interface.

### Streamlit Dashboard

The application provides:

* Airport selector
* Conversational chat interface
* Current operational metrics
* Copilot response
* Agent activity
* RAG trace
* Guardrail status
* Human approval interface
* Execution result
* Audit information

---

## 3. System Architecture

```text
                         ┌──────────────────────┐
                         │     Streamlit UI     │
                         │      app.py          │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │   Airport           │
                         │   Orchestrator      │
                         └──────────┬───────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    │               │               │
                    ▼               ▼               ▼
          ┌────────────────┐ ┌──────────────┐ ┌──────────────┐
          │  Operations    │ │   Policy &   │ │  Resolution  │
          │  Investigator  │ │  Compliance  │ │    Agent     │
          └───────┬────────┘ └──────┬───────┘ └──────────────┘
                  │                 │
                  ▼                 ▼
          ┌──────────────┐  ┌──────────────────┐
          │ Airport      │  │ RAG + FAISS      │
          │ Metrics      │  │ Policy Retrieval │
          └──────────────┘  └──────────────────┘
                                    │
                                    ▼
                           ┌──────────────────┐
                           │ Gemini Embedding │
                           │ + Gemini LLM     │
                           └──────────────────┘

                                    │
                                    ▼
                           ┌──────────────────┐
                           │    Guardrails    │
                           └────────┬─────────┘
                                    │
                     ┌──────────────┴──────────────┐
                     │                             │
                     ▼                             ▼
             Low/Medium Risk                 High Risk
                     │                             │
                     ▼                             ▼
              Tool Execution              Human Approval
                                                   │
                                                   ▼
                                            Action Execution
                                                   │
                                                   ▼
                                             Audit Record
```

---

## 4. RAG Pipeline

The policy question-answering pipeline follows these steps:

```text
Policy Documents
       │
       ▼
Document Loading
       │
       ▼
Text Cleaning
       │
       ▼
Semantic Section Chunking
       │
       ▼
Gemini Embeddings
       │
       ▼
FAISS Vector Store
       │
       ▼
Similarity Search
       │
       ▼
Relevant Policy Sections
       │
       ▼
Gemini LLM
       │
       ▼
Policy-Grounded Answer
```

### Chunking Strategy

The project uses **semantic section-based chunking** rather than blindly splitting documents at a fixed character count.

Policy documents use Markdown headings such as:

```text
## Queue Management
## Completion Rate
## ETA Guidelines
## Surge Policy
```

The loader splits documents around these sections so that related policy information remains together.

The current policy corpus produces **49 semantic chunks**.

### Embeddings

The project uses:

```text
gemini-embedding-001
```

The generated embedding vectors have a dimension of:

```text
3072
```

### Vector Database

FAISS is used for efficient similarity search.

The vector store uses:

```text
IndexFlatIP
```

with normalized embeddings for cosine-style similarity comparison.

Generated files:

```text
data/vector_store/airport_policy.index
data/vector_store/chunks.json
```

---

## 5. Airport Policy Examples

The project contains policies for:

```text
SFO
LAX
JFK
```

### SFO

Example operational thresholds:

| Metric                   | Threshold |
| ------------------------ | --------: |
| Queue - Elevated         |     > 150 |
| Queue - Investigation    |     > 200 |
| Expected Completion Rate |     > 85% |
| Critical Completion Rate |     < 75% |
| ETA Target               |  < 15 min |
| Severe ETA               |  > 20 min |
| Maximum Surge            |      1.5x |
| Approval Threshold       |    > 1.3x |

### LAX

| Metric                   | Threshold |
| ------------------------ | --------: |
| Queue - Elevated         |     > 160 |
| Queue - Investigation    |     > 220 |
| Expected Completion Rate |     > 84% |
| Critical Completion Rate |     < 74% |
| ETA Target               |  < 16 min |
| Severe ETA               |  > 22 min |
| Maximum Surge            |      1.4x |
| Approval Threshold       |    > 1.2x |

### JFK

| Metric                   | Threshold |
| ------------------------ | --------: |
| Queue - Elevated         |     > 140 |
| Queue - Investigation    |     > 200 |
| Expected Completion Rate |     > 86% |
| Critical Completion Rate |     < 76% |
| ETA Target               |  < 14 min |
| Severe ETA               |  > 20 min |
| Maximum Surge            |      1.6x |
| Approval Threshold       |    > 1.3x |

---

## 6. Multi-Agent Workflow

The orchestrator coordinates specialized agents.

### Operations Investigator

Retrieves airport telemetry and evaluates the operational situation.

Example:

```text
Queue Size: 125
Active Drivers: 192
Average ETA: 12.1 min
Completion Rate: 92%
Cancellation Rate: 6%
Surge: 1.0x
```

### Policy & Compliance Agent

Uses RAG to retrieve relevant airport policy sections.

It provides:

* Policy answer
* Source documents
* Airport
* Section
* Similarity score

### Resolution Agent

Combines operational findings and policy information to determine an appropriate resolution.

The workflow supports a ReAct-style multi-step reasoning process with a maximum of **5 iterations**.

---

## 7. Operational Tools

### `get_airport_metrics`

Retrieves the latest available airport telemetry.

Example output:

```text
airport: SFO
queue_size: 125
active_drivers: 192
request_volume: 405
completion_rate: 0.92
driver_cancellation_rate: 0.06
avg_eta_minutes: 12.1
surge_multiplier: 1.0
```

### `calculate_driver_incentive`

Calculates an incentive based on operational pressure.

Current synthetic rules:

| Queue Size | Incentive |
| ---------- | --------: |
| > 200      |      ₹500 |
| > 150      |      ₹300 |
| > 100      |      ₹150 |
| ≤ 100      |        ₹0 |

### `trigger_surge_override`

Validates and processes a requested surge multiplier.

The tool checks:

1. Supported airport
2. Maximum allowed surge
3. Approval threshold
4. Approval status
5. Execution eligibility

---

## 8. Guardrails and Risk Classification

Before an operational action is executed, it passes through guardrails.

The workflow is:

```text
User Request
     │
     ▼
Input Validation
     │
     ▼
Risk Classification
     │
     ▼
Action Validation
     │
     ├── Invalid → Block
     │
     ├── Low/Medium → Execute
     │
     └── High Risk
             │
             ▼
       Human Approval
             │
       ┌─────┴─────┐
       ▼           ▼
    Approved     Rejected
       │           │
       ▼           ▼
    Execute       Stop
       │
       ▼
   Audit Record
```

### Example

Request:

```text
Increase SFO surge to 1.4x
```

SFO's approval threshold is `1.3x`, while its maximum allowed surge is `1.5x`.

Therefore:

```text
Risk: HIGH
Human Approval: REQUIRED
Maximum Allowed: 1.5x
Approval Threshold: 1.3x
```

After approval:

```text
Surge override approved and ready for execution.
```

A request such as:

```text
Increase SFO surge to 2.0x
```

is blocked because it exceeds the airport's maximum allowed surge.

---

## 9. Human-in-the-Loop

High-risk actions are not automatically executed.

The Streamlit application displays:

```text
Human Approval Required
```

The operator can select:

```text
Approve
```

or

```text
Reject
```

The approval decision is recorded together with:

* Airport
* Requested multiplier
* Approval threshold
* Maximum allowed multiplier
* Approver
* Execution status
* Audit information

---

## 10. Audit Trail

Operational actions generate audit records containing information such as:

```text
timestamp
airport
action
requested value
risk level
approval requirement
approval decision
approved by
execution result
```

This provides traceability for operational decisions.

---

## 11. Conversational Memory

The copilot includes a conversation memory component that stores recent interaction history.

The memory layer supports:

* Adding messages
* Retrieving conversation history
* Retrieving recent messages
* Clearing history
* Formatting history for agent context

This allows follow-up questions to maintain conversational context.

---

## 12. Project Structure

```text
airport-ai-copilot/
│
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
├── pytest.ini
├── app.py
│
├── data/
│   ├── airport_policies/
│   │   ├── sfo_operations.md
│   │   ├── sfo_pricing.md
│   │   ├── sfo_driver_policy.md
│   │   ├── lax_operations.md
│   │   ├── lax_pricing.md
│   │   ├── jfk_operations.md
│   │   └── jfk_pricing.md
│   │
│   └── airport_metrics.csv
│
├── notebooks/
│   ├── day1_rag_pipeline.ipynb
│   ├── day2_tools.ipynb
│   ├── day3_agents.ipynb
│   └── day4_guardrails.ipynb
│
├── src/
│   ├── __init__.py
│   ├── config.py
│   ├── document_loader.py
│   ├── vector_store.py
│   ├── tools.py
│   ├── agents.py
│   ├── memory.py
│   ├── guardrails.py
│   └── prompts.py
│
└── output/
    └── distilled_training_data.jsonl
```

---

## 13. Technology Stack

| Component            | Technology                         |
| -------------------- | ---------------------------------- |
| Programming Language | Python 3.12                        |
| LLM                  | Google Gemini                      |
| Embeddings           | Gemini `gemini-embedding-001`      |
| Vector Database      | FAISS                              |
| Data Processing      | Pandas / NumPy                     |
| RAG                  | Custom semantic retrieval pipeline |
| Agent System         | Python multi-agent orchestration   |
| UI                   | Streamlit                          |
| Testing              | Pytest                             |
| Configuration        | python-dotenv                      |
| Version Control      | Git / GitHub                       |

---

## 14. Installation

Clone the repository:

```bash
git clone https://github.com/charviha/Airport-Operations-AI-Copilot.git
cd Airport-Operations-AI-Copilot
```

Create the virtual environment:

```bash
python3 -m venv .venv
```

Activate it:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

## 15. Environment Configuration

Create the `.env` file:

```bash
cp .env.example .env
```

Open it:

```bash
nano .env
```

Add your Gemini API key:

```text
GEMINI_API_KEY=your_gemini_api_key_here
```

The `.env` file is excluded from Git using `.gitignore`.

---

## 16. Build the Policy Vector Store

From the project root:

```bash
python -m src.vector_store
```

This creates:

```text
data/vector_store/airport_policy.index
data/vector_store/chunks.json
```

---

## 17. Run the Backend

To test the agent system directly:

```bash
python -m src.agents
```

This runs example airport-operation queries and displays:

* Guardrail classification
* Airport metrics
* Policy information
* Agent execution trace
* Resolution
* Action status

---

## 18. Run the Streamlit Application

Start the application:

```bash
streamlit run app.py
```

The application will be available at:

```text
http://localhost:8501
```

---

## 19. Example Queries

### Operational Investigation

```text
SFO queue is high. What should we do?
```

The system retrieves current SFO metrics and compares them with SFO policy thresholds.

### Policy Question

```text
What is the maximum surge multiplier at SFO?
```

The RAG system retrieves the relevant SFO pricing policy.

### High-Risk Action

```text
Increase SFO surge to 1.4x
```

The system identifies that approval is required and waits for human confirmation.

### Invalid Action

```text
Increase SFO surge to 2.0x
```

The request is blocked because it exceeds the SFO maximum surge limit.

### Airport-Specific Query

```text
What is the current situation at LAX?
```

The system identifies LAX and retrieves LAX-specific operational information.

---

## 20. Testing

The project uses Pytest for automated testing.

Run:

```bash
pytest -q
```

Current test result:

```text
26 passed
```

The test suite covers the implemented RAG and guardrail functionality, including:

* Input validation
* Risk classification
* Surge validation
* Human approval workflow
* Action validation
* Audit records
* RAG retrieval
* Policy answering

---

## 21. Distilled Training Data

The project also generates distilled JSONL examples representing operational decision scenarios.

Location:

```text
output/distilled_training_data.jsonl
```

The examples include:

* Low-risk requests
* Medium-risk requests
* High-risk requests
* Approved actions
* Rejected actions
* Blocked actions

This dataset can be used for future evaluation or model improvement experiments.

---

## 22. Example End-to-End Flow

Consider:

```text
User:
Increase SFO surge to 1.4x
```

### Step 1 — Airport Detection

The orchestrator identifies:

```text
Airport = SFO
```

### Step 2 — Guardrail Classification

```text
Risk = HIGH
```

### Step 3 — Policy Validation

The policy specifies:

```text
Approval Threshold = 1.3x
Maximum Surge = 1.5x
```

### Step 4 — Human Approval

The request is placed into a pending state.

```text
Human Approval Required
```

### Step 5 — Operator Decision

The operator approves the request.

### Step 6 — Execution

The surge override is validated and marked ready for execution.

### Step 7 — Audit

An audit record is generated containing the request, approval, and execution information.

---

## 23. Project Outcomes

The completed copilot demonstrates an end-to-end agentic AI workflow combining:

```text
RAG
+
Operational Telemetry
+
Tool Calling
+
Multi-Agent Reasoning
+
Guardrails
+
Human Approval
+
Auditability
+
Streamlit UI
```

The architecture separates **information retrieval**, **operational investigation**, **policy compliance**, **resolution**, and **action execution**, allowing the system to provide grounded operational assistance while controlling higher-risk actions through explicit approval.

---

## 24. Future Enhancements

Potential extensions include:

* Live airport telemetry integration
* Real-time event streaming
* Additional airports
* More operational tools
* Role-based approval workflows
* Persistent production database
* Advanced agent observability
* Evaluation dashboards
* Automated policy versioning
* Production authentication and authorization
* Cloud deployment
* Integration with airport operations systems

---

## 25. Author

**Airport Operations AI Copilot**

Built as an agentic AI project demonstrating:

* Retrieval-Augmented Generation
* LLM application development
* Multi-agent systems
* Tool calling
* Guardrails
* Human-in-the-loop workflows
* Operational analytics
* AI application development
