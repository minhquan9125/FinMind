# Frozen user-oriented acceptance scenarios v1

Authored independently by an isolated AI agent acting as a Vietnamese FinMind user/QA, from the parent task's business requirements only. This is not a claim of true human-blind evaluation.

The author did not inspect production code, existing tests, datasets, reports, git history, or other agents' work. Only mandatory skill instructions and the author's own artifact-writing process were accessed. No runtime output or implementation behavior informed expectations.

Frozen artifact: `scenarios.jsonl`, UTF-8 without BOM, one JSON object per line, LF newlines. Exactly 32 unique questions, IDs USER-001 through USER-032. Freeze occurs at this write, before any runtime feedback; scenarios must not be edited in response to execution results. Revisions require a separate version.

SHA256 (exact bytes of scenarios.jsonl): `b9fc8f2eaf509bfb8309b9f64d37f6712532e32c42eb3e11fb23d9b373fbc3e6`

Groups: clear=10; ambiguous=5; multi=5; context=4; failure=6; scope=2. The final eight cases comprise fallback/scope/error coverage.

Expected objective labels express business concepts only; no internal route, trace, reason, classifier enum, dataset values, or citations are prescribed. Required periods use natural canonical years/dates. When a multipart question has different periods, required_period is null and must_preserve binds each objective to its own period.

NEVER prohibits classification AI for genuinely clear cases; it does not prohibit distinct grounded answer-generation AI. UNCONSTRAINED does not require fallback invocation. Failure injection is limited to six deliberately difficult meaning-analysis questions. Runner output must separately report whether each provider scenario was reached; an unreached injected condition is not evidence the condition passed. Ambiguity must remain a clarification request even if a provider suggests an unrelated intent.

Technical data accuracy, live source availability, and citation contents cannot be established by this business-only oracle. SERVE means address the specified research objective with available grounded evidence; it does not authorize fabricated data. Context contains user messages only and does not assert unseen assistant behavior.
