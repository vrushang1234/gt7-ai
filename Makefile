-include .env

PYTHON ?= python
IP ?=

.PHONY: run record clean clean-maps clean-logs clean-cache help

help:
	@echo "Targets:"
	@echo "  make run IP=<ps_ip>      - run live telemetry"
	@echo "  make record IP=<ps_ip>   - run + write JSONL log"
	@echo "  make clean               - remove maps, turns, logs, pycache"
	@echo "  make clean-maps          - remove maps/ dir"
	@echo "  make clean-turns         - remove turns/ dir"
	@echo "  make clean-logs          - remove logs/ dir"
	@echo "  make clean-cache         - remove __pycache__"

_check_ip:
	@if [ -z "$(IP)" ]; then echo "IP not set. Use: make run IP=192.168.x.x"; exit 1; fi

run: _check_ip
	$(PYTHON) main.py $(IP)

record: _check_ip
	$(PYTHON) main.py $(IP) --record

clean: clean-maps clean-turns clean-logs clean-cache

clean-maps:
	rm -rf maps

clean-turns:
	rm -rf turns

clean-logs:
	rm -rf logs

clean-cache:
	rm -rf __pycache__ */__pycache__
