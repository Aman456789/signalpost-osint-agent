INPUT ?= data/input/companies.txt

.PHONY: install run test demo pilot baseline replay api web

install:
	python3.12 -m venv .venv
	.venv/bin/pip install -r requirements.txt
	cd frontend && npm install

run:
	bash scripts/run_one.sh $(INPUT)

test:
	pytest tests -q

demo:
	bash scripts/run_one.sh $(INPUT) --pass1-only

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
