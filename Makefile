.PHONY: run test demo pilot baseline replay api web

run:
	bash scripts/run_one.sh data/input/companies.txt

test:
	pytest tests -q

demo:
	bash scripts/run_one.sh data/input/companies.txt --pass1-only

pilot:
	bash scripts/run_pilot.sh

baseline:
	bash scripts/run_baseline.sh

replay:
	@echo "not built yet"

api:
	uvicorn api.main:app --reload

web:
	cd frontend && npm run dev
