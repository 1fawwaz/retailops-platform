\# CLAUDE.md — RetailOps AI Platform



\*\*Read this file before every task. It is the standing contract for this repository.\*\*



\---



\## 1. What this project is



A two-service retail intelligence platform, built as a flagship portfolio project for roles in software engineering, AI engineering, data engineering, and data analytics. It must read as production work, not a student demo. Correctness, honesty, and reviewability matter more than feature count.



\- \*\*`stockpilot-core/`\*\* — headless FastAPI + PostgreSQL retail operations API with demand forecasting. No frontend.

\- \*\*`retailops-ai/`\*\* — LangGraph multi-agent layer that reasons over StockPilot's HTTP API. Owns the only UI.



The two services communicate \*\*only over HTTP\*\*, with \*\*separate databases\*\*. This boundary is the central architectural claim of the project and may not be crossed for convenience.



\## 2. Starting state



\*\*Absolute zero.\*\* Nothing was built before this repository. There is no legacy code, no pre-existing schema, no partially complete service. If something appears to be missing, it is missing because it has not been written yet — build it per the specification, do not assume it exists elsewhere.



\## 3. The canonical specification



`docs/BUILD-SPEC.md` is the single source of truth. It is \*\*frozen\*\*.



\- Follow it exactly. Do not redesign the architecture.

\- Do not add components it does not list. Do not remove components it does list.

\- If you believe something in the spec is wrong or infeasible, \*\*stop and say so\*\*. Do not silently deviate.

\- Improvement ideas go in Appendix D of the spec as unchecked items. They are not implemented during this build.



\## 4. The three invariants (never weaken)



1\. \*\*Grounding.\*\* Every numeric claim traces to a `tool\_call\_id` and carries a provenance label. The Decision Engine and Report agents have \*\*zero tools\*\* by design. A runtime Citation Validator rejects any output containing an uncited or unlabelled number.

2\. \*\*Full trace.\*\* Every execution persists its plan, agent steps, tool calls with raw responses, prompt version hashes, model IDs, token counts, and timings.

3\. \*\*Untrusted data.\*\* Retrieved business data is untrusted input. It enters prompts inside a delimited envelope declaring it data, never instruction.



\*\*Corollary — the LLM never computes a business number.\*\* Revenue at risk, inventory cost, confidence, and priority are computed in Python from cited inputs. The LLM writes explanatory prose only.



\## 5. Data provenance



Every metric carries one of four labels, threaded through schema, API responses, agent outputs, and UI:



| Label | Meaning |

|---|---|

| `observed` | Directly from the source dataset |

| `derived` | Deterministically computed via a documented method |

| `predicted` | Output of the forecasting model |

| `inferred` | Reserved; avoid |



Provenance is \*\*never upgraded\*\*. A value computed from a `predicted` input stays `predicted`.



\## 6. Tech stack (pinned — do not substitute)



| Layer | Choice |

|---|---|

| Language | Python 3.11 |

| API | FastAPI, Uvicorn |

| ORM / migrations | SQLAlchemy 2.x, Alembic |

| Validation | Pydantic v2 |

| Database | PostgreSQL 16 |

| Containers | Docker, Docker Compose |

| Agents | LangGraph, LangChain (tools/messages primitives only) |

| LLM | Google Gemini via a provider interface |

| ML / data | scikit-learn, pandas, NumPy |

| Testing | pytest, pytest-asyncio |

| Quality | ruff, mypy |

| CI | GitHub Actions |

| Frontend | Next.js (App Router), React, TypeScript, Tailwind |



\## 7. Model configuration



Lives in `retailops-ai/config/models.yaml`. \*\*No model name may appear anywhere in code.\*\*



```yaml

roles:

&#x20; planner:   gemini-3.1-pro      # strongest reasoning; planning and replanning

&#x20; retriever: gemini-3.5-flash    # inventory / forecast / analytics agents

&#x20; decision:  gemini-3.1-pro      # Decision Engine prose only

budgets:

&#x20; max\_tool\_iterations: 12

&#x20; max\_tokens\_per\_execution: 60000

```



\*\*Verify these IDs against the provider's model-list endpoint before first use\*\* — Gemini model strings move fast and availability varies by region and tier. Do not use any Gemini 2.5 model: that generation is scheduled for shutdown in October 2026.



No provider SDK may be imported outside `retailops-ai/llm/providers/`. The rest of the codebase sees one interface: `generate()`, `generate\_structured()`, `stream()`.



\## 8. Coding rules



\- \*\*Strict typing.\*\* Full annotations. `mypy --strict` clean. No bare `Any` — if you genuinely need it, add a comment justifying it.

\- \*\*No hardcoded values.\*\* URLs, keys, thresholds, model names, table names: config or env only.

\- \*\*Clean layering.\*\* `api/ → orchestration/ → agents/ → tools/ → clients/`. No upward imports, no skipping more than one level down.

\- \*\*No placeholders.\*\* No `TODO`, no `pass  # implement later`, no stub returning fake data. If you cannot finish something, stop and say so rather than shipping a shell.

\- \*\*No mock data presented as real.\*\* Ever.

\- \*\*Tests with every task.\*\* ≥80% coverage on business logic, agents, tools, and the validator.

\- PEP 8 via ruff. SOLID where it earns its keep — do not add abstraction layers the spec does not call for.



\## 9. Workflow protocol (this is the important section)



\*\*One task per session turn. Never generate the whole project, a whole phase, or a whole part in one go.\*\*



For each task:



1\. Restate the task and what "done" means before writing code.

2\. Implement only that task.

3\. Run `ruff`, `mypy`, and `pytest`. Fix every failure.

4\. Verify the task's milestone check from the spec actually passes — run it, don't assume.

5\. Commit with a clear message.

6\. \*\*Report and stop.\*\* Wait for approval before the next task.



Do not begin the next task because it seems obvious. Do not batch commits. Do not refactor code from an earlier task without being asked.



\## 10. Definition of done (per task)



\- \[ ] `pytest` passes, no skipped tests

\- \[ ] `ruff` clean

\- \[ ] `mypy` clean

\- \[ ] Docker builds

\- \[ ] The task's milestone check verified by running it

\- \[ ] Endpoints appear correctly in OpenAPI/Swagger

\- \[ ] No TODOs, stubs, or placeholder returns

\- \[ ] Committed



\*\*End of day rule:\*\* the system must boot. Never end a day mid-refactor with nothing runnable. If a day's milestone can't be met, cut its scope rather than carrying broken code forward.



\## 11. Stop and ask — do not guess



Halt and ask when:



\- The spec is ambiguous or appears contradictory

\- A needed StockPilot endpoint doesn't exist (log it in `docs/stockpilot-gaps.md` first)

\- You'd have to fabricate, simulate, or default a business value to proceed

\- A library or model ID in the stack is unavailable or deprecated

\- A task can't be completed without breaking an invariant or a coding rule

\- The dataset doesn't contain a field the task assumes



A blocked task reported honestly is a good outcome. A task completed by inventing something is not.



\## 12. Environment



Windows 11, VS Code, Docker Desktop, Git, Python 3.11, Claude Code CLI. Prefer cross-platform commands. Use `docker compose` (v2 syntax). Make targets should work in PowerShell.



\## 13. Secrets



`.env` is gitignored and never read into a commit, a log, or a chat response. `.env.example` is committed with empty values:



```

DATABASE\_URL=

POSTGRES\_USER=

POSTGRES\_PASSWORD=

POSTGRES\_DB=

RETAILOPS\_DATABASE\_URL=

STOCKPILOT\_BASE\_URL=

GEMINI\_API\_KEY=

JWT\_SECRET=

JWT\_ALGORITHM=HS256

```



Never print a secret's value. Never suggest committing one. If a key is needed and missing, say which one and stop.



\## 14. Dataset



Online Retail II (UCI / Kaggle, CC BY 4.0). Lives in `data/`, gitignored, fetched by `scripts/download\_data.py` with a checksum so the pipeline is reproducible on a clean machine. Attribution goes in the README.



The dataset has \*\*no\*\* cost price, stock levels, suppliers, or categories. All four are derived by a seeded, documented script and labelled `derived` everywhere they surface. This is disclosed plainly in the README, not buried.



\## 15. Git



Single repository, `main` branch, MIT licence. Commit after every task. Tag milestones: `day-0-bootstrap`, `stockpilot-core-complete`, `retailops-phase-1`, `retailops-phase-2`, `v1.0`.



Commit messages: what changed and why, imperative mood, one line plus body if needed. No "wip", no "fixes", no emoji.



\## 16. Honesty



No metric appears in any README, doc, or commit message unless it was measured — and the doc states how it was measured. Every limitation gets written down. If the forecasting model loses to the seasonal-naive baseline, ship the baseline and report both scores.



This rule is not negotiable. The entire value of this project rests on it being true.

