-include .env
export

PYTHON ?= python
IP ?=

.PHONY: run record analyze dashboard dashboard-install clean clean-maps clean-turns clean-logs clean-tactics clean-audio clean-cache help

help:
	@echo "Targets:"
	@echo "  make run IP=<ps_ip>      - run live telemetry"
	@echo "  make record IP=<ps_ip>   - run + write JSONL log"
	@echo "  make analyze             - find best entry/exit per turn from logs/"
	@echo "  make dashboard           - run vite dev server"
	@echo "  make clean               - remove maps, turns, logs, tactics, pycache"
	@echo "  make clean-maps          - remove maps/ dir"
	@echo "  make clean-turns         - remove turns/ dir"
	@echo "  make clean-logs          - remove logs/ dir"
	@echo "  make clean-tactics       - remove tactics/ dir"
	@echo "  make clean-audio         - remove audio/ dir"
	@echo "  make clean-cache         - remove __pycache__"

_check_ip:
	@if [ -z "$(IP)" ]; then echo "IP not set. Use: make run IP=192.168.x.x"; exit 1; fi

run: _check_ip
	$(PYTHON) main.py $(IP)

record: _check_ip
	$(PYTHON) main.py $(IP) --record

analyze:
	$(PYTHON) analyze.py

dashboard:
	cd dashboard && npm run dev

clean: clean-maps clean-turns clean-logs clean-tactics clean-audio clean-cache

clean-tactics:
	rm -rf tactics

clean-audio:
	rm -rf audio

clean-maps:
	rm -rf maps

clean-turns:
	rm -rf turns

clean-logs:
	rm -rf logs

clean-cache:
	rm -rf __pycache__ */__pycache__
