.PHONY: run test demo replay baseline

run:
	python -m agent_engine.cli run --input data/input/companies.txt

test:
	pytest -q

demo:
	python -m agent_engine.cli run --input data/input/companies.txt

replay:
	@echo "not built yet"

baseline:
	@echo "not built yet"
