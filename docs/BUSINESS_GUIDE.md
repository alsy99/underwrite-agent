# Underwrite Agent — Business & Credit Risk Guide

**Audience:** business, product, credit risk, fraud ops, compliance — not engineers.  
**Purpose:** explain what the system does, how work flows, and what “Sherlock Investigation” means in practice.

---

## 1. One-sentence product

Underwrite Agent is an **advisory fraud-investigation assistant** for complex loans. It reads the document package, checks stories against each other and against bank policy, runs open-source / registry-style checks, and produces an **auditable case file** with a recommended action for a human underwriter.

It does **not** replace the underwriter, the loan origination system (LOS), or the bank’s final credit decision.

---

## 2. Who it is for

| Role | Why they care |
|------|----------------|
| **Credit / fraud underwriters** | Faster packet review; contradictions and OSINT signals in one place |
| **Credit risk / MRM** | Clear advisory boundary, audit trail, human-in-the-loop |
| **Product / GTM** | Demoable wedge: investigation, not “full LOS replacement” |
| **Ops / lenders** | Works beside existing LOS and spreading tools |
| **Compliance** | Policy checks from bank-owned policy docs; no silent auto-decline to customer |

**Loan types supported today**

1. SBA 7(a)  
2. CRE acquisition  
3. Specialty / bank-statement mortgage  

---

## 3. What problem it solves

Complex packages (applications, VOEs, bank statements, leases, P&Ls) often tell **inconsistent stories**. Manual checklists miss mismatches; generic chatbots don’t produce a structured, cited case file.

Underwrite Agent focuses on three jobs:

1. **Find contradictions** across documents (with quotes / citations).  
2. **Check bank policy** at investigation time (policies uploaded by the bank).  
3. **Profile entities** (business, employer, address, principals) via OSINT-style checks and attach risk signals.

Optional follow-ons already in product: upload a **financial spread**, generate a **draft credit memo**, and **notify an LOS** when a case finishes.

---

## 4. End-to-end workflow (business view)

```text
  Loan packet uploaded
          │
          ▼
  Documents stored & prepared
          │
          ▼
  ┌─────────────────────────────────────┐
  │     Sherlock Investigation          │
  │  1. Cross-check narratives          │
  │  2. Policy compliance check         │
  │  3. Plan follow-up checks           │
  │  4. Run tools (registry, OSINT…)    │
  │  5. Build entity profiles           │
  │  6. Write executive brief           │
  │  7. Freeze case file + audit log    │
  └─────────────────────────────────────┘
          │
          ▼
  Underwriter reviews case file
  (optional: spread upload, memo draft)
          │
          ▼
  Human decision in bank process / LOS
```

### Step by step

| Step | What happens | What the human sees |
|------|----------------|---------------------|
| **Intake** | Packet uploaded (UI, API, or LOS push). Case queued. | Case ID, status “queued / processing” |
| **Prepare docs** | Files classified and text extracted; sensitive IDs masked before AI prompts. | (Behind the scenes) |
| **Sherlock runs** | Automated investigation (see §5). | Progress; then completed case file |
| **Review** | Underwriter reads summary, findings, contradictions, OSINT profiles, open questions. | Demo UI case page or API export |
| **Optional spread** | Analyst uploads CSV/Excel; system flags variance vs stated income/revenue. | Variance list on case |
| **Optional memo** | System drafts a citation-backed memo for editing. | Markdown draft |
| **Optional LOS notify** | Bank systems can receive “case completed” (and related) events. | Downstream LOS / ops tools |
| **Decision** | Human decides; adverse action / approval stays in bank process. | Not automated by this product |

---

## 5. Sherlock Investigation (plain language)

**Sherlock** is the name for the **automated investigation workflow** that builds the case file. Think of it as a junior investigator that always leaves a paper trail.

### 5.1 Stages (in order)

1. **Intake** — Load the case and documents; pull key facts from text when possible (business name, employer, address, EIN, applicant).  
2. **Cross-check** — Compare stories across documents (e.g. employer on application vs employment letter; stated income vs deposits). Flag contradictions with severity and evidence snippets.  
3. **Policy check** — Retrieve relevant bank policy rules and score the packet (pass / review / fail style findings).  
4. **Plan** — Decide which follow-up checks are worth running (registry, employer match, address risk, sanctions, web presence, etc.).  
5. **Investigate (tools)** — Run those checks within a step limit. Each call is logged.  
6. **Profile** — Combine results into **entity profiles** (business, employer, principal, address) with status such as corroborated, partial, mismatch, or flagged.  
7. **Brief** — Write a short executive summary for the underwriter.  
8. **Finalize** — Save the case file, mark completed, keep the full audit timeline.

### 5.2 Outputs Sherlock produces

| Output | Meaning for credit risk |
|--------|-------------------------|
| **Executive summary** | Narrative overview grounded in findings |
| **Findings** | Structured issues (contradictions, policy, OSINT) |
| **Contradictions** | Document A says X; document B says Y — with quotes |
| **Policy findings** | Bank rule references and status |
| **Entity profiles** | Who/what was checked externally and how risky it looks |
| **Open questions** | What a human should still verify |
| **Recommended action** | `approve` / `review` / `decline` — **advisory only** |
| **Audit trail** | Who/what ran, when, with hashed inputs and outputs |

### 5.3 How recommendations are meant to be used

| Recommendation | Typical interpretation |
|----------------|------------------------|
| **approve** | No material contradictions; policies look clean; OSINT not flagged — still subject to human sign-off |
| **review** | Something needs eyes (contradiction, policy review/fail, or OSINT mismatch/flag) |
| **decline** | Multiple independent high-severity signals — escalate; **not** an automatic customer decline letter |

**Always:** a human underwriter (or designated authority) makes the credit decision.

---

## 6. Systems map (non-technical)

You do not need to know how servers work. Conceptually:

| Piece | Role in the business process |
|-------|------------------------------|
| **Demo / workbench UI** | Upload packets, watch investigations, read case files, upload spreads, generate memo drafts |
| **API** | Secure doorway for apps and LOS integrations |
| **Worker / Sherlock engine** | Runs the investigation jobs in the background |
| **Document store** | Keeps raw files by lender (“tenant”) |
| **Database** | Cases, audit events, spreads, memos, webhook registrations |
| **Bank policies** | Uploaded policy docs used at investigation time (no code change to update policy text) |
| **OSINT / registry checks** | External or fixture-backed checks for entity existence, address risk, sanctions, etc. |
| **LOS hooks (optional)** | Notify or pull/push packages so ops stay in their system of record |

**Tenants:** each lender (or business unit) is separated by a tenant id — policies and cases stay in their lane.

**Access (enterprise shape):** shared automation keys and/or company login (OIDC). Roles roughly:

- **Underwriter** — create work, upload spreads, generate memos  
- **Reviewer** — read cases and audit  
- **Admin** — manage integrations such as webhooks  

---

## 7. After Sherlock: spreading, memo, LOS

These sit **around** the investigation; they do not replace it.

| Capability | Business value |
|------------|----------------|
| **Spreading** | Compare uploaded financials to stated income/revenue; surface variance for review |
| **Credit memo draft** | Start from the case file (findings, OSINT, variances) so underwriters edit instead of blank-page drafting |
| **LOS webhooks / export** | Push “case completed”, “memo ready”, high variance events into bank orchestration — or pull a full export JSON |

Named connectors (e.g. Encompass, nCino) are a later packaging step; the **generic** integration path exists today.

---

## 8. Trust, risk, and what not to claim

### Safe claims

- Speeds investigation of unstructured packages  
- Produces cited findings and an audit trail  
- Keeps humans in the decision loop  
- Supports bank-specific policy documents  

### Do not claim

- “Replaces underwriters”  
- “Fully automated underwriting / LOS”  
- “Enterprise KYC coverage” without contracted data vendors and legal review  
- That demo / fixture accuracy equals live portfolio performance  

### Controls credit risk should know

- Outputs are **advisory**  
- Sensitive IDs are masked before model prompts  
- Investigation steps are **logged**  
- OSINT may use demo fixtures or live sources depending on bank configuration and keys  
- Model-risk one-pager: [MRM_COMPLIANCE.md](MRM_COMPLIANCE.md)  

---

## 9. Example stories (for demos)

**Clean path** — Documents agree; registry looks active; address ordinary → recommendation often leans **approve** / light review.

**Fraud-ish path** — Application employer “Acme”, employment letter “Beta”; income vs deposits diverge; address looks like a mail drop → contradictions + OSINT **mismatch/flagged** → **review** or compound **decline** signal for escalation.

Use these as **illustrations**, not guarantees of every live file’s outcome.

---

## 10. Roles & RACI (lightweight)

| Activity | Underwriter | Credit risk | Product | IT / vendor ops |
|----------|-------------|-------------|---------|-----------------|
| Upload / start investigation | R | C | I | C |
| Interpret case file | R | C | I | — |
| Update bank policies in product | C | A/R | C | C |
| Enable live OSINT / LOS hooks | C | C | C | R |
| Final credit decision | R | A (policy) | — | — |
| Model monitoring / agreement sampling | C | R | C | C |

R = responsible, A = accountable, C = consulted, I = informed (simplified).

---

## 11. Glossary

| Term | Plain meaning |
|------|----------------|
| **Case file** | Structured investigation result the underwriter reads |
| **Sherlock** | The automated investigation workflow |
| **Contradiction** | Two documents disagree on a material fact |
| **OSINT** | Open / public / registry-style checks on entities and addresses |
| **Entity profile** | Summary of OSINT results for one party or address |
| **Policy RAG** | “Ask the bank’s policy documents” during the investigation |
| **Advisory recommendation** | Suggested action, not a binding decision |
| **Audit trail** | Time-ordered log of investigation steps |
| **Spread** | Tabular financials (CSV/Excel) compared to stated figures |
| **LOS** | Loan origination system (bank’s main lending system) |

---

## 12. Where to go next

| If you need… | Read |
|--------------|------|
| Sales / ICP positioning | [GTM_POSITIONING.md](GTM_POSITIONING.md) |
| Roadmap / what’s shipped | [PRODUCT_ROADMAP.md](PRODUCT_ROADMAP.md) |
| Model risk committee | [MRM_COMPLIANCE.md](MRM_COMPLIANCE.md) |
| Enterprise auth / deploy | [ENTERPRISE.md](ENTERPRISE.md), [SSO.md](SSO.md) |
| Spreading / memo / LOS detail | [SPREADING.md](SPREADING.md), [MEMO.md](MEMO.md), [LOS_WEBHOOKS.md](LOS_WEBHOOKS.md) |
| Technical architecture | [ARCHITECTURE.md](ARCHITECTURE.md) |

---

## Appendix A — Exec deck outline (10 slides)

1. **Title** — Underwrite Agent: advisory fraud investigation for complex lending  
2. **Problem** — Unstructured packets; missed narrative fraud; slow manual review  
3. **Solution** — Sherlock investigation → cited case file; human decides  
4. **Who** — SBA / CRE / bank-statement specialty lenders  
5. **Workflow** — Upload → Sherlock → review → (spread/memo) → LOS / decision  
6. **Sherlock stages** — Cross-check → policy → OSINT tools → profiles → brief  
7. **Outputs** — Findings, profiles, open questions, approve/review/decline (advisory)  
8. **Trust** — Audit trail, PII masking, human-in-the-loop, MRM posture  
9. **Fit with stack** — Beside LOS & spreading; optional webhooks/memo  
10. **Ask** — Pilot on labeled packets; success = underwriter time saved + agreement rate  

---

*Document version aligned with product roadmap phases A–D (SSO, spreading, memo, LOS). For questions on live data vendors or production pilots, involve legal + credit risk before go-live.*
