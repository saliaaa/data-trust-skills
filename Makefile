.PHONY: demo test evals validate ci

demo:
	uv run python examples/broken-revenue-demo/run_demo.py

test:
	uv run pytest

evals:
	uv run python evals/run_evals.py

validate:
	uv run python scripts/validate_skills.py

ci: validate test evals
