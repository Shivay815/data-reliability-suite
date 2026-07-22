.PHONY: setup data contracts collect chaos all

PLATFORM_DIR := ../ecom-analytics-platform

setup:            ## install python deps
	pip install -r requirements.txt

data:             ## build Project A (raw data + dbt artifacts to monitor)
	@if [ ! -d $(PLATFORM_DIR) ]; then \
		git clone --depth 1 https://github.com/Shivay815/ecom-analytics-platform $(PLATFORM_DIR); \
	fi
	cd $(PLATFORM_DIR) && pip install -r requirements.txt && $(MAKE) load build
	cd $(PLATFORM_DIR) && dbt source freshness --project-dir dbt --profiles-dir dbt

contracts:        ## run GX ingestion contracts against raw data
	python run_contracts.py

collect:          ## append dbt + model health to reliability history
	python collectors/collect_dbt_health.py
	python collectors/collect_model_health.py

chaos:            ## chaos drills: prove contracts catch injected breaks
	pytest tests/ -q

all: data contracts collect chaos
