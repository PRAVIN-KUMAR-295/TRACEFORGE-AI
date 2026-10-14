# TRACEFORGE AI ⚡
### AI-Powered Software Incident Investigator with FalkorDB Graph & Persistent Memory

> **Graph Hacks 2026 Submission** | **Theme: Context for AI Agents**  
> *Tracks Addressed: Agents That Act on Connected Data • Agent Memory and Coordination • Company Brain*

---

## 1. Product Vision & Problem

When complex software systems experience cascading outages, on-call engineers are inundated with disconnected alerts, fragmented logs, and opaque distributed traces. Ordinary chatbots fail during incident triage because:
1. **They lack topological relationship awareness** — they cannot trace how a database connection pool leak in a tier-3 auth dependency triggers a circuit-breaker trip in an edge checkout service.
2. **They hallucinate causes without verifiable proof** — they cannot point to concrete graph query paths confirming facts versus hypotheses.
3. **They lack cross-session operational memory** — past postmortems and proven remedies are forgotten, leading to repeat outages.

**TRACEFORGE AI** solves this by putting **FalkorDB graph relationships** and **persistent incident memory** at the core of the investigation pipeline. When an incident occurs, TRACEFORGE executes native OpenCypher queries backwards through the dependency graph, identifies upstream code deployments and infrastructure bottlenecks, links past validated resolutions, and proposes actionable remediation steps under strict **Human-in-the-Loop** control.

---

## 2. Architecture & Graph Data Model

```
                    ┌────────────────────────────────────────────────────────┐
                    │          TRACEFORGE AI React Frontend (Vite/TS)        │
                    │  Dark Developer SaaS • Interactive Graph Visualizer    │
                    │  Confirmed Facts vs Hypotheses • Cypher Console • HITL │
                    └───────────────────────────┬────────────────────────────┘
                                                │ REST / JSON (Port 8000)
                                                ▼
                    ┌────────────────────────────────────────────────────────┐
                    │               FastAPI High-Performance API             │
                    │  Routers: /api/investigations, /api/graph, /api/memory  │
                    └───────────┬───────────────────────────────┬────────────┘
                                │                               │
       ┌────────────────────────┴──────────────┐   ┌────────────┴──────────────┐
       │     Investigation & Memory Engine     │   │     LLM Provider Gateway  │
       │  • Multi-Hop Graph Traversal          │   │  • Deterministic Engine   │
       │  • Confirmed Facts vs Hypotheses      │   │  • OpenAI / Claude        │
       │  • Postmortem Resolution Transfer     │   │  • Gemini / Groq / Ollama │
       └────────────────────────┬──────────────┘   └───────────────────────────┘
                                │ OpenCypher
                                ▼
                    ┌────────────────────────────────────────────────────────┐
                    │                 FalkorDB Graph Engine                  │
                    │                                                        │
                    │  Nodes:                                                │
                    │   • (:Service)        • (:Database)   • (:Queue)       │
                    │   • (:Deployment)     • (:ErrorPattern)                │
                    │   • (:MetricAnomaly)  • (:Incident)   • (:Resolution)  │
                    │                                                        │
                    │  Relationships:                                        │
                    │   • [:DEPENDS_ON]     • [:CONNECTS_TO]                 │
                    │   • [:DEPLOYED_TO]    • [:AFFECTS]                     │
                    │   • [:TRIGGERED_BY]   • [:CAUSED_BY]                   │
                    │   • [:RESOLVED_BY]    • [:SIMILAR_TO]                  │
                    │                                                        │
                    │  Dual Mode:                                            │
                    │   1. Live FalkorDB Server (Cloud or Docker)            │
                    │   2. In-Memory OpenCypher Engine (Local fallback)      │
                    └────────────────────────────────────────────────────────┘
```

---

## 3. Core Features

### A. Graph-Based Incident Investigation
- Select or input an incident (e.g. `INC-2026-1042: Payment & Checkout Cascade Outage`).
- Executes multi-hop OpenCypher queries to traverse dependencies, database links, and recent deployments.
- Clearly separates **Confirmed Facts** (100% verified via graph queries with inspectable Cypher proofs) from **Root-Cause Hypotheses** (ranked by confidence with full causal cascade paths).

### B. Persistent Cross-Session Memory
- Retains past incident postmortems, root causes, and proven fixes inside FalkorDB.
- Computes graph similarity against historical precedents (e.g. `INC-2026-0814: Auth Token Starvation Cascade` with 94% similarity).
- Explains **why** a past incident influenced the current recommendation.
- Allows recording new resolved postmortems into FalkorDB memory directly from the UI.

### C. Interactive Graph Explorer
- Visualizes microservice topologies, data stores, deployments, and error cascades.
- Filter by node types (`Service`, `Incident`, `Database`, `Deployment`, `ErrorPattern`, `MetricAnomaly`, `Resolution`).
- Inspect node properties, connections, and owners via the slide-out inspector drawer.
- Path highlighting: visually isolates the exact causal cascade path on the canvas.

### D. Actionable Remediation (Human-in-the-Loop)
- Generates precise remediation actions (`CONFIG_UPDATE`, `ROLLBACK`, `CIRCUIT_BREAKER`).
- Displays dry-run simulation output and risk levels (`LOW`, `MEDIUM`, `HIGH`).
- **Strict Human Approval Gate**: automated state changes are permanently disabled. An engineer must explicitly inspect the dry run and enter approval credentials before changes take effect.

### E. Live OpenCypher Query Console
- Test arbitrary OpenCypher queries against the graph database with sub-millisecond execution times.
- Preset template queries for instant graph inspection.
- Full audit log of all Cypher queries executed during automated investigations.

---

## 4. FalkorDB Integration & Rule Compliance

TRACEFORGE AI strictly complies with the Graph Hacks 2026 requirement that **FalkorDB is central and functional**, not decorative:
- Every investigation step generates and evaluates real Cypher queries:
  ```cypher
  MATCH (i:Incident {id: $incident_id})-[r:AFFECTS]->(s:Service) RETURN i, r, s
  MATCH (s:Service)-[r:DEPENDS_ON]->(dep:Service) WHERE s.id = $service_id RETURN s, r, dep
  MATCH (d:Deployment)-[r:DEPLOYED_TO]->(s:Service) RETURN d, r, s
  MATCH (i:Incident)-[r:SIMILAR_TO]->(h:Incident)-[:RESOLVED_BY]->(res:Resolution) RETURN i, h, res
  ```
- **Zero Hardcoded Mock Responses**: Node topologies, edge traversals, and neighbor discoveries are computed dynamically against the graph database.
- **Dual-Engine Architecture**: Connects seamlessly to a live FalkorDB cluster or FalkorDB Cloud instance via the official `falkordb` Python client. When a live FalkorDB server is offline, it automatically falls back to an internal FalkorDB-compatible Property Graph Cypher Engine, ensuring anyone evaluating the project can run it instantly without mandatory external containers.

---

## 5. Quick Start & Setup Guide

### Prerequisites
- Python 3.10+ (Tested on Python 3.14)
- Node.js 18+ (Tested on Node.js 24)
- *(Optional)* Docker (if running local FalkorDB container)

### Step 1: Clone and Set Up Backend
```bash
# Navigate to project directory
cd "TRACEFORGE AI"

# Create and activate Python virtual environment
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install pinned dependencies
pip install -r requirements.txt
```

### Step 2: Configure Environment Variables
Copy the example environment file:
```bash
cp .env.example .env
```
Default configuration works immediately with **Deterministic Demo Mode**:
```ini
APP_NAME="TRACEFORGE AI"
FALKORDB_HOST=localhost
FALKORDB_PORT=6379
FALKORDB_GRAPH_NAME=traceforge_incidents
LLM_PROVIDER=demo
DEMO_MODE=true
```

*(Optional)* To use a live FalkorDB instance:
```bash
# Start FalkorDB with Docker:
docker run -p 6379:6379 -it --rm falkordb/falkordb:latest
```

*(Optional)* To use an external LLM provider, set in `.env`:
```ini
LLM_PROVIDER=openai # or gemini, anthropic, groq, ollama
LLM_API_KEY=your_api_key_here
LLM_MODEL=gpt-4o-mini # or gemini-1.5-flash, claude-3-5-sonnet
```

### Step 3: Run the Backend Server
```bash
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```
The FastAPI backend will start at: `http://127.0.0.1:8000`  
Interactive Swagger API docs: `http://127.0.0.1:8000/docs`

### Step 4: Run the Frontend
In a new terminal:
```bash
cd frontend
npm install
npm run dev
```
Open your browser at `http://localhost:5173`.

---

## 6. One-Click Demo Experience

1. Open `http://localhost:5173`.
2. Click the **"1-Click Demo"** button in the top navigation bar.
3. TRACEFORGE AI automatically:
   - Queries FalkorDB for active incident `INC-2026-1042`.
   - Traces dependencies: `api-gateway` → `checkout-service` → `auth-service` → `redis-auth-cache`.
   - Pinpoints `deploy-auth-v2.4.1` deployed 28 minutes prior with connection pool limits reduced to 50.
   - Synthesizes 3 Confirmed Facts and 2 Hypotheses with Cypher query proofs.
   - Recalls historical match `INC-2026-0814` (94% similarity) and explains its influence.
   - Proposes 3 actionable mitigations awaiting human approval.
4. Click **"Approve & Execute"** on the Redis connection pool hotfix to verify the safe mitigation workflow.

---

## 7. Automated Test Suite

Run the full backend test suite verifying Cypher evaluation, integration, and remediation:
```bash
.\venv\Scripts\python.exe -m pytest backend/tests -v
```
All 8 automated integration tests pass:
- `test_memory_graph_engine_basic_crud`
- `test_cypher_match_node`
- `test_cypher_match_relationship`
- `test_falkordb_client_execute_cypher`
- `test_subgraph_neighborhood`
- `test_end_to_end_investigation`
- `test_persistent_memory_storage_and_search`
- `test_human_approval_remediation_workflow`

---

## 8. Limitations & Future Roadmap

- **Multi-Cloud Autonomous Agents**: Add bi-directional Slack and PagerDuty bot integrations for conversational triage.
- **Dynamic Cypher Synthesis**: Expand natural language-to-Cypher generation using FalkorDB GraphRAG embeddings for arbitrary unindexed schemas.
- **Chaos Engineering Integration**: Automated fault-injection validation in staging environments prior to production action execution.

---

## 9. License

MIT License. Built for Graph Hacks 2026.
