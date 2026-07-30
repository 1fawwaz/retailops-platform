.PHONY: setup db-up db-down ingest test eval run-core run-agents generate-models

setup:
	py -3.11 -m venv stockpilot-core/.venv
	py -3.11 -m venv retailops-ai/.venv
	stockpilot-core/.venv/Scripts/python.exe -m pip install --upgrade pip
	stockpilot-core/.venv/Scripts/python.exe -m pip install -e "stockpilot-core[dev]"
	retailops-ai/.venv/Scripts/python.exe -m pip install --upgrade pip
	retailops-ai/.venv/Scripts/python.exe -m pip install -e "retailops-ai[dev]"
	python -m pre_commit install

db-up:
	docker compose up -d

db-down:
	docker compose down

ingest:
	stockpilot-core/.venv/Scripts/python.exe stockpilot-core/scripts/download_data.py
	stockpilot-core/.venv/Scripts/python.exe -m stockpilot_core.scripts.run_etl

test:
	stockpilot-core/.venv/Scripts/python.exe -m pytest stockpilot-core/tests
	retailops-ai/.venv/Scripts/python.exe -m pytest retailops-ai/tests

eval:
	cd retailops-ai && ../retailops-ai/.venv/Scripts/python.exe evals/run.py

run-core:
	stockpilot-core/.venv/Scripts/uvicorn.exe api.main:app --app-dir stockpilot-core --reload --port 8000

run-agents:
	retailops-ai/.venv/Scripts/uvicorn.exe api.main:app --app-dir retailops-ai --reload --port 8001

generate-models:
	cd retailops-ai && ../retailops-ai/.venv/Scripts/python.exe -m datamodel_code_generator \
		--input ../contracts/stockpilot-api/versions/v1.json \
		--input-file-type openapi \
		--output clients/stockpilot_models.py \
		--output-model-type pydantic_v2.BaseModel \
		--target-python-version 3.11 \
		--use-schema-description \
		--use-standard-collections \
		--use-union-operator \
		--use-annotated \
		--output-datetime-class datetime
	retailops-ai/.venv/Scripts/python.exe -m ruff format retailops-ai/clients/stockpilot_models.py
