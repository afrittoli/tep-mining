.PHONY: help lint type-check test check parse scan-gaps gap-report mine-pr-cache map-prs pr-map-report fetch-tep-prs fetch-impl-prs report-index search synthesize query explorer apply-pr-overrides apply-export validate-conventions permissions worktree-classify worktree-remove

# Load .env if it exists
-include .env
export

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

lint: ## Lint Python with ruff and Markdown with markdownlint
	uv run ruff check scripts/ tests/
	uv run ruff format --check scripts/ tests/
	npx --yes markdownlint-cli "**/*.md" --ignore node_modules --ignore .venv

type-check: ## Run mypy type checks over scripts/
	uv run mypy scripts/

test: ## Run pytest unit tests
	uv run pytest --tb=short -q

check: lint type-check test validate-conventions ## Run all static checks and tests

parse: ## Sub-Task 2: Parse TEP .md files → raw/teps.jsonl
	uv run scripts/parse_teps.py \
		--teps-dir "$(COMMUNITY_REPO_PATH)/teps" \
		--output raw/teps.jsonl

scan-gaps: ## Sub-Task 2b: Scan GitHub for missing TEP numbers → raw/tep_gaps.jsonl + stubs in raw/teps.jsonl
	uv run scripts/scan_tep_gaps.py \
		--teps-jsonl raw/teps.jsonl \
		--gaps-out raw/tep_gaps.jsonl \
		--max-tep 173 \
		--rename 190:171 \
		--rename 191:172 \
		--rename 192:173

gap-report: ## Sub-Task 2c: Render HTML gap report → reports/gap_report.html
	uv run scripts/gap_report.py \
		--gaps raw/tep_gaps.jsonl \
		--teps raw/teps.jsonl \
		--out reports/gap_report.html

mine-pr-cache: ## Mine merged PR metadata into raw/community_pr_cache.jsonl
	uv run scripts/mine_pr_cache.py \
		--repo tektoncd/community \
		--cache raw/community_pr_cache.jsonl

map-prs: ## Sub-Task 3: Discover TEP proposal PR numbers from cached PR metadata → raw/tep_pr_map.json
	uv run scripts/map_tep_prs.py \
		--cache raw/community_pr_cache.jsonl \
		--teps-jsonl raw/teps.jsonl \
		--output raw/tep_pr_map.json

pr-map-report: ## Render HTML PR mapping report → reports/pr_map_report.html
	uv run scripts/pr_map_report.py \
		--map raw/tep_pr_map.json \
		--teps raw/teps.jsonl \
		--out reports/pr_map_report.html

fetch-tep-prs: ## Sub-Task 4: Fetch TEP proposal PR review threads → raw/community_prs.jsonl
	uv run scripts/fetch_tep_prs.py \
		--pr-map raw/tep_pr_map.json \
		--output-prs raw/community_prs.jsonl \
		--output-reviews raw/community_pr_reviews.jsonl \
		--report reports/tep_pr_reviews.html

fetch-impl-prs: ## Sub-Task 5: Fetch implementation PR metadata → raw/impl_prs.jsonl
	uv run scripts/fetch_impl_prs.py \
		--teps-jsonl raw/teps.jsonl \
		--output-prs raw/impl_prs.jsonl \
		--output-reviews raw/impl_pr_reviews.jsonl \
		--report reports/impl_prs_report.html

report-index: ## Build a tabbed index over every reports/*.html → reports/index.html
	uv run scripts/build_report_index.py \
		--reports-dir reports \
		--out reports/index.html

search: ## Sub-Task 6: Cross-repo TEP reference search (run after fetch-impl-prs)
	uv run scripts/cross_repo_search.py \
		--teps-jsonl raw/teps.jsonl \
		--tep-pr-map raw/tep_pr_map.json \
		--impl-prs-jsonl raw/impl_prs.jsonl \
		--output-reviews raw/impl_pr_reviews.jsonl \
		--discoveries-out raw/impl_pr_discoveries.json \
		--processed-dir processed \
		--report reports/cross_repo_search_report.html

apply-pr-overrides: ## Fetch metadata for "include" overrides not yet in raw/impl_prs.jsonl (run before synthesize)
	uv run scripts/apply_pr_overrides.py \
		--overrides overrides/pr_attribution_overrides.jsonl \
		--impl-prs raw/impl_prs.jsonl \
		--output-reviews raw/impl_pr_reviews.jsonl

apply-export: ## Merge an explorer-exported corrections file into overrides/*.jsonl, e.g. make apply-export FILE=~/Downloads/pr_attribution_overrides.export.jsonl
	uv run scripts/apply_export.py "$(FILE)"

validate-conventions: ## Validate conventions/*.yaml structural invariants (Sub-Task 8)
	uv run scripts/validate_conventions.py conventions/*.yaml

synthesize: ## Sub-Task 7: Join raw data into per-TEP records → processed/
	uv run scripts/synthesize.py \
		--teps-jsonl raw/teps.jsonl \
		--tep-pr-map raw/tep_pr_map.json \
		--community-prs raw/community_prs.jsonl \
		--community-reviews raw/community_pr_reviews.jsonl \
		--impl-prs raw/impl_prs.jsonl \
		--impl-reviews raw/impl_pr_reviews.jsonl \
		--discoveries raw/impl_pr_discoveries.json \
		--gaps raw/tep_gaps.jsonl \
		--coverage processed/latest/coverage.json \
		--overrides overrides/section_overrides.jsonl \
		--pr-overrides overrides/pr_attribution_overrides.jsonl \
		--known-commits overrides/known_commits.jsonl \
		--processed-dir processed

explorer: ## Build the interactive TEP data explorer (run after synthesize) → reports/explorer.html
	uv run scripts/build_explorer.py \
		--records processed/latest/per_tep_records.json \
		--classifications processed/latest/comment_classifications.jsonl \
		--out reports/explorer.html

query: ## Launch an interactive DuckDB session over every raw/processed JSONL file
	uv run scripts/query_console.py

# --- Parallel classification (Sub-Task 8, see parallel-classify-plan.md) ---

permissions: ## Manage agent permissions. MODE=parallel (classify) | MODE=safe (locked down) | no MODE (status)
	uv run scripts/manage_permissions.py --mode $(if $(MODE),$(MODE),status)

worktree-classify: ## Create an isolated worktree for classifying one TEP. Usage: make worktree-classify TEP=76
ifndef TEP
	$(error TEP is not set. Usage: make worktree-classify TEP=<N>)
endif
	@if ! git show HEAD:.claude/settings.json | uv run python3 -c 'import json,sys; d=json.load(sys.stdin); sys.exit(0 if d["permissions"]["allow"] else 1)'; then \
		echo "Permissions are not in parallel mode as of HEAD (.claude/settings.json has an empty allow list)." >&2; \
		echo "A new worktree checks out whatever is COMMITTED, not uncommitted changes in this checkout." >&2; \
		echo "Run 'make permissions MODE=parallel', commit .claude/settings.json and .bob/settings.json on main, then retry." >&2; \
		exit 1; \
	fi
	@if [ -d ../tep-mining-tep$(TEP) ]; then \
		echo "cd ../tep-mining-tep$(TEP)"; \
	else \
		git worktree add ../tep-mining-tep$(TEP) -b classify/tep$(TEP) >&2 && \
		echo "cd ../tep-mining-tep$(TEP)"; \
	fi

worktree-remove: ## Remove a per-TEP worktree and its branch after its commit is merged. Usage: make worktree-remove TEP=76
ifndef TEP
	$(error TEP is not set. Usage: make worktree-remove TEP=<N>)
endif
	git worktree remove ../tep-mining-tep$(TEP) --force
	git branch -d classify/tep$(TEP)
