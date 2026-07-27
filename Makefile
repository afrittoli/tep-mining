.PHONY: help lint type-check test check parse scan-gaps gap-report mine-pr-cache map-prs pr-map-report fetch-tep-prs fetch-impl-prs report-index search synthesize query

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

check: lint type-check test ## Run all static checks and tests

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

synthesize: ## Sub-Task 7: Join raw data into per-TEP records → processed/
	uv run scripts/synthesize.py \
		--teps-jsonl raw/teps.jsonl \
		--pr-map raw/tep_pr_map.json \
		--community-prs raw/community_prs.jsonl \
		--community-reviews raw/community_pr_reviews.jsonl \
		--impl-prs raw/impl_prs.jsonl \
		--impl-reviews raw/impl_pr_reviews.jsonl

query: ## Launch an interactive DuckDB session over the raw JSONL files
	uv run python -c "\
import duckdb; \
con = duckdb.connect(); \
con.execute(\"CREATE VIEW teps AS SELECT * FROM read_json_auto('raw/teps.jsonl', format='newline_delimited')\"); \
print('Tables: teps'); \
print('Type SQL queries, or .quit to exit.'); \
con.sql('.mode column'); \
import readline, atexit; \
from pathlib import Path; \
hist = Path.home() / '.duckdb_history'; \
try: readline.read_history_file(hist); \
except FileNotFoundError: pass; \
atexit.register(readline.write_history_file, hist); \
while True: \
    try: q = input('duckdb> '); \
    except (EOFError, KeyboardInterrupt): break; \
    if q.strip() in ('.quit', '.exit', 'quit', 'exit'): break; \
    if q.strip(): \
        try: con.sql(q).show(); \
        except Exception as e: print(f'Error: {e}') \
"
