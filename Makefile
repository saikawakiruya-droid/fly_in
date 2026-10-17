# Fly-in: common tasks (subject chapter III.2).
#
#   make install        create .venv (if absent) and install requirements.txt
#   make run            run the default map; override with MAP=... ARGS=...
#                       e.g. make run MAP=maps/x.txt ARGS="--visual both"
#   make debug          the same, under pdb
#   make clean          remove caches (__pycache__, .mypy_cache, ...)
#   make lint           flake8 + mypy with the flags the subject requires
#   make lint-strict    flake8 + mypy --strict
#   make test           run the unit tests (tests/)
#   make fclean         clean, and remove .venv as well

VENV := .venv
MAP ?= maps/subject_example.txt
ARGS ?=

ifeq ($(OS),Windows_NT)
    PYTHON_SYS ?= python
    VENV_BIN := $(VENV)/Scripts
else
    PYTHON_SYS ?= python3
    VENV_BIN := $(VENV)/bin
endif

PYTHON := $(VENV_BIN)/python
STAMP := $(VENV)/.installed
MYPY_FLAGS := --warn-return-any --warn-unused-ignores \
    --ignore-missing-imports --disallow-untyped-defs --check-untyped-defs
CACHES := __pycache__ .mypy_cache .pytest_cache

.PHONY: install run debug clean fclean lint lint-strict test

install:
	test -d $(VENV) || $(PYTHON_SYS) -m venv $(VENV)
	$(PYTHON) -m pip install -r requirements.txt
	@touch $(STAMP)

# Targets that use the virtual environment install it first if needed.
$(STAMP): requirements.txt
	$(MAKE) install

run: $(STAMP)
	$(PYTHON) fly_in.py $(MAP) $(ARGS)

debug: $(STAMP)
	$(PYTHON) -m pdb fly_in.py $(MAP) $(ARGS)

clean:
	find . -path ./$(VENV) -prune -o -type d \
	    \( $(patsubst %,-name % -o,$(CACHES)) -false \) -prune \
	    -exec rm -rf {} +
	find . -path ./$(VENV) -prune -o -type f -name '*.py[co]' \
	    -exec rm -f {} +

fclean: clean
	rm -rf $(VENV)

lint: $(STAMP)
	$(PYTHON) -m flake8 .
	$(PYTHON) -m mypy . $(MYPY_FLAGS)

lint-strict: $(STAMP)
	$(PYTHON) -m flake8 .
	$(PYTHON) -m mypy . --strict

test: $(STAMP)
	$(PYTHON) -m pytest tests -q
