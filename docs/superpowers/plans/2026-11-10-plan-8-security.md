# Apollo Predictor, Plan 8 (optional): Security and Bug Pass

**Goal:** Scan Apollo for security problems with free, offline tools, sort every finding, and fix the real ones test-first.

**Spec:** `docs/superpowers/specs/2026-11-08-apollo-predictor-design.md`, section 5.16.

## Global Constraints

- Free tools only. No paid model, no API key.
- The scanners live in `~/.venvs/vulnclaw`, never in Apollo's dependencies.
- Nothing outside this laptop is tested. The pentest targets `127.0.0.1` only, and only with a local Ollama model.
- Raw scanner output goes to `reports/security/`, which git ignores. The triage goes to `docs/reviews/security-<date>.md`.

## Tasks

- [x] **1. Install.** Create `~/.venvs/vulnclaw`. Install VulnClaw pinned to a commit, plus `pip-audit` and `bandit`.
- [x] **2. Scan.** Run `vulnclaw code scan --layer L1` and `--layer L2` with `--format sarif` on `src/`, `web/src/`, `.github/workflows/` and `config/`. Run `bandit -r src`, `pip-audit` on the frozen environment, and `npm audit` in `web/`.
- [x] **3. Skip what needs a model.** L3 and the local pentest run only if `ollama` is installed. Record the skip.
- [x] **4. Triage.** Read the code behind every finding. Mark each one real, false positive or accepted risk in the review file.
- [x] **5. Fix.** Each real finding gets a failing test, then the fix. Run the full suite.
- [x] **6. Whole-repo review.** `/code-review` after the scan (spec 5.16). Findings are listed in the review file, not yet fixed.
