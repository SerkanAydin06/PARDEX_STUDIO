# Phase 2D — Independent Quality & Matched A/B

**Purpose:** prevent self-review and compare provider performance without invented token/cost claims. The previous phase's approved job queue remains the only way to invoke AI.

## Implemented
1. Normal/Critical General Manager plans register a dependent independent QA task. The reviewer provider must differ from the coding provider, both when scheduled and on actual run.
2. Reviewer output must contain one final `PARDEX_QA_VERDICT=PASS` or `PARDEX_QA_VERDICT=FAIL` followed by `PARDEX_QA_FINDINGS=` with a bounded summary. Missing evidence, failing local engine test, mismatched actual provider or FAIL blocks acceptance. The owner separately accepts PASS.
3. QA contracts bind evidence to producer/reviewer attempt counts. Later attempts invalidate the older gate. Short redacted findings and verdicts are stored in the local private task database, not raw code or prompts.
4. A/B pilot creation requires no AI invocation. It records exact task-hash, engine, shared test profile and two selected AI providers. Trials must be finished, owner-reviewed task attempts from different project directories using identical task text and engine. Three complete pairs are required before a preliminary comparison display.
5. GUI options in AI General Manager: independent QA report, create pilot, inspect pilots, link selected measured task to pilot.

## Explicit limitations
- Model PASS is **only an untrusted claim**, not formal code review or security certification.
- The true editor and tester isolation of model CLIs is NOT guaranteed by this feature; prompt instructions are not permission boundaries. An isolated, resource-limited reviewer environment is still planned for phase 2E.
- Pilot copies and identical toolchain versions are owner-attested, not independently proven. Even three trial pairs cannot establish statistical superiority.
- Supported engine tests are not available in every local environment. An untested engine fails closed.
- Actual token/credit consumption, subscription remaining quotas, pricing, and profitability cannot be inferred from CLI wall-clock durations.
- No extra AI requests, autonomous model switches, purchases, deployments or global policy changes are triggered by QA dashboards or pilot planning.

## Test and rollback
Run `python -m unittest discover -s tests -p 'test_*.py' -q` and `python -m compileall -q app tests`. Follow CI status for this PR. Rollback by reverting the PR; private database records remain local and no project game code is modified by the migration.

## Follow-up: 2E
Add read-only/isolated code reviewer sandboxes, diff fingerprinting, a reproducible versioned test corpus and measured provider token usage only where available. Keep owner approval before any core merge or paid action.
