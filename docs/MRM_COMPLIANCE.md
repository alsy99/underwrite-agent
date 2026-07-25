# Model risk & compliance one-pager

For risk committees evaluating Underwrite Agent as an **advisory decision-support** tool.

## System purpose

Automate fraud-oriented investigation over loan document packets: contradiction detection, policy retrieval, OSINT profiling. Recommend `approve` / `review` / `decline` for **human** underwriter action.

## Model inventory (summary)

| Component | Type | Notes |
|-----------|------|-------|
| Cross-check LLM | Generative + rules | Falls back to heuristics if LLM unavailable |
| Policy RAG | Retrieval + LLM/heuristic evaluate | Tenant-scoped policy chunks |
| Investigation planner | LLM JSON tool plan | Bounded by `MAX_AGENT_STEPS` |
| Executive brief | Generative summary | Grounded on structured findings |
| Embeddings | Local sentence-transformers or Azure | Document / policy similarity |
| OSINT ProfileAnalyzer | Deterministic fusion | No generative step |

## Controls already in product

- **Human-in-the-loop** — recommendations advisory; UI/API expose open questions
- **Audit trail** — tool calls, plans, outputs hashed/stored per case
- **PII redaction** — SSN / EIN / account patterns stripped before LLM prompts
- **Tenant soft isolation** — `tenant_id` on records and object storage prefixes
- **Version tags** — `prompt_version` on audit events
- **Eval harness** — fixture golden set metrics ([OSINT_EVAL.md](OSINT_EVAL.md))

## Limitations (disclose)

- OSINT live coverage is key/cache dependent; demos use fixtures
- Golden-set F1 is **not** a production portfolio backtest
- No adverse-action letter automation (ECOA/FCRA process stays with lender)
- Not a substitute for CIP/KYC vendor of record

## Challenger / monitoring expectations

1. Run `python scripts/eval_osint.py` in CI; fail on F1 floor regressions
2. Sample production cases for underwriter agreement rate (manual until labeled set exists)
3. Log provider mode (`fixture` vs `live`) on OSINT tool outputs for drift review
4. Re-validate after prompt, model, or provider changes

## Owner checklist before bank pilot

- [ ] Legal review of live OSINT ToS
- [ ] MRM inventory entry + model owner named
- [ ] Strong API key / network controls ([ENTERPRISE.md](ENTERPRISE.md))
- [ ] Written procedure: underwriter must review `review`/`decline` before adverse action
