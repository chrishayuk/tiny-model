# tiny-model monorepo Makefile
#
# Run from the repo root. Paths are relative to here so that the
# knowledge-extractor CLI's default `datasets/{raw,extracted}/` resolves
# correctly. `uv run --project <dir>` keeps the current working directory
# while using the subproject's virtualenv.

KE         := knowledge-extractor
BENCH      := benchmarks
TOKENIZER  := tokenizer

UV_KE      := uv run --project $(KE)
UV_BENCH   := uv run --project $(BENCH)
CARGO      := cargo --manifest-path $(TOKENIZER)/Cargo.toml

.DEFAULT_GOAL := help

.PHONY: help
help:
	@echo "tiny-model targets:"
	@echo ""
	@echo "  setup            install python deps + build tokenizer (one-time)"
	@echo "  sync             re-sync python venvs (after dep changes)"
	@echo ""
	@echo "  demo             run the knowledge-extractor demo (~50ms)"
	@echo "  list             list registered datasets"
	@echo ""
	@echo "  download         download raw sources for tier 1"
	@echo "  extract          extract triples from raw (assumes download done)"
	@echo "  run              download + extract for tier 1"
	@echo "  run-NAME         run a single dataset, e.g. 'make run-osm-gb'"
	@echo "  download-NAME    download a single dataset (no extract)"
	@echo "  extract-NAME     extract a single dataset (assumes raw present)"
	@echo "                   valid names:  wordnet morphology framenet verbnet"
	@echo "                                 collocations wikidata osm-gb"
	@echo "                                 treesitter standards"
	@echo ""
	@echo "  stats            summarise datasets/extracted/"
	@echo "  verify           verify extracted manifest consistency"
	@echo "  coverage         run benchmark coverage analysis"
	@echo ""
	@echo "  test             rust + python tests"
	@echo "  tokenizer-build  cargo build --release the tokenizer workspace"
	@echo "  tokenizer-test   cargo test the tokenizer workspace"
	@echo ""
	@echo "  clean            remove build artifacts + python caches"
	@echo "  clean-datasets   remove datasets/raw/ and datasets/extracted/"
	@echo "                   (legacy snapshot in datasets/extracted-legacy/ is preserved)"

# ----------------------------------------------------------------------
# setup
# ----------------------------------------------------------------------

.PHONY: setup
setup: sync tokenizer-build

.PHONY: sync
sync:
	cd $(KE) && uv sync
	cd $(BENCH) && uv sync

# ----------------------------------------------------------------------
# knowledge-extractor
# ----------------------------------------------------------------------

.PHONY: demo
demo:
	$(UV_KE) python $(KE)/examples/run_demo.py

.PHONY: list
list:
	$(UV_KE) knowledge-extractor list

.PHONY: download
download:
	$(UV_KE) knowledge-extractor download --tier 1

.PHONY: extract
extract:
	$(UV_KE) knowledge-extractor extract --tier 1

.PHONY: run
run:
	$(UV_KE) knowledge-extractor run --tier 1

# ----------------------------------------------------------------------
# per-dataset phase targets
# ----------------------------------------------------------------------
#
# One source of truth for the registered datasets. For each entry, we
# generate three targets from the short name (the part after the slash):
#
#   make run-<name>       download + extract
#   make download-<name>  just populate raw_dir
#   make extract-<name>   just transform raw -> triples
#
# Example: for "knowledge/osm-gb" you get run-osm-gb, download-osm-gb,
# and extract-osm-gb. Adding a new dataset is one line in DATASETS.

DATASETS := \
	linguistics/wordnet \
	linguistics/morphology \
	linguistics/framenet \
	linguistics/verbnet \
	linguistics/collocations \
	knowledge/wikidata \
	knowledge/osm-gb \
	ast/treesitter \
	domain/standards

define _phase_targets
.PHONY: run-$(notdir $(1)) download-$(notdir $(1)) extract-$(notdir $(1))
run-$(notdir $(1)):      ; $$(UV_KE) knowledge-extractor run $(1)
download-$(notdir $(1)): ; $$(UV_KE) knowledge-extractor download $(1)
extract-$(notdir $(1)):  ; $$(UV_KE) knowledge-extractor extract $(1)
endef

$(foreach d,$(DATASETS),$(eval $(call _phase_targets,$d)))

.PHONY: stats
stats:
	$(UV_KE) knowledge-extractor stats datasets/extracted/

.PHONY: verify
verify:
	$(UV_KE) knowledge-extractor verify datasets/extracted/

# ----------------------------------------------------------------------
# benchmarks
# ----------------------------------------------------------------------

.PHONY: coverage
coverage:
	$(UV_BENCH) python $(BENCH)/benchmark_coverage.py \
	    --data-dir datasets/extracted/ \
	    --output $(BENCH)/results/

# ----------------------------------------------------------------------
# tokenizer (rust workspace + python binding)
# ----------------------------------------------------------------------

.PHONY: tokenizer-build
tokenizer-build:
	$(CARGO) build --release

.PHONY: tokenizer-test
tokenizer-test:
	$(CARGO) test

# ----------------------------------------------------------------------
# composite
# ----------------------------------------------------------------------

.PHONY: test
test: tokenizer-test ke-test

.PHONY: ke-test
ke-test:
	$(UV_KE) --extra dev --extra osm pytest $(KE)/tests/

# ----------------------------------------------------------------------
# clean
# ----------------------------------------------------------------------

.PHONY: clean
clean:
	$(CARGO) clean
	find . -type d -name __pycache__ -not -path '*/target/*' -prune -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name '.pytest_cache' -prune -exec rm -rf {} + 2>/dev/null || true

.PHONY: clean-datasets
clean-datasets:
	rm -rf datasets/raw datasets/extracted
