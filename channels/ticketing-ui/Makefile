# Delegate Docker/stack targets to repo root (see ../../Makefile).
ROOT := ../..
.PHONY: help
help:
	@$(MAKE) -C $(ROOT) help

%:
	@$(MAKE) -C $(ROOT) $@
