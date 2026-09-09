PROFILE ?= fast
SYSTEMS ?= direct reference

.PHONY: wall run report site test all

wall:            ## start the fake provider (PROFILE=fast|full)
	python -m failoverbench wall --profile $(PROFILE) -v

run:             ## run every system in SYSTEMS through the catalogue
	@for s in $(SYSTEMS); do python -m failoverbench run --system systems/$$s.yaml --profile $(PROFILE); done

report:          ## render results/$(PROFILE)/SCORECARD.md
	python -m failoverbench report --profile $(PROFILE)

site:            ## render docs/index.html from results/$(PROFILE)
	python -m failoverbench site --profile $(PROFILE)

test:            ## smoke tests (no external packages needed)
	python tests/test_smoke.py
	python tests/test_inband_error.py
	python tests/test_templating.py
	python tests/test_scoring.py

all: run report
