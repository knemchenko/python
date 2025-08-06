# Makefile for the project

# --- Variables ---
PYTHON = python3
VENV_DIR = venv
VENV_ACTIVATE = . $(VENV_DIR)/bin/activate

# --- Setup ---
.PHONY: init
init:
	@echo "--- Creating virtual environment in $(VENV_DIR) ---"
	@$(PYTHON) -m venv $(VENV_DIR)
	@echo "--- Installing development dependencies ---"
	@$(VENV_ACTIVATE) && pip install --upgrade pip
	@$(VENV_ACTIVATE) && pip install -r requirements-dev.txt
	@echo "--- Environment setup complete. Activate with: source $(VENV_DIR)/bin/activate ---"

.PHONY: clean
clean:
	@echo "--- Cleaning up ---"
	@rm -rf $(VENV_DIR)
	@rm -rf .mypy_cache .pytest_cache .coverage htmlcov
	@find . -type d -name "__pycache__" -exec rm -r {} +

# --- Dependencies ---
.PHONY: compile
compile:
	@echo "--- Compiling requirements.txt from requirements.in ---"
	@$(VENV_ACTIVATE) && pip-compile --upgrade -o requirements.txt requirements.in
	@echo "--- Compiling requirements-dev.txt from requirements-dev.in ---"
	@$(VENV_ACTIVATE) && pip-compile --upgrade -o requirements-dev.txt requirements-dev.in

# --- Quality ---
.PHONY: lint
lint:
	@echo "--- Running ruff linter ---"
	@$(VENV_ACTIVATE) && ruff check src tests scripts
	@echo "--- Running ruff formatter (check mode) ---"
	@$(VENV_ACTIVATE) && ruff format --check src tests scripts

.PHONY: format
format:
	@echo "--- Formatting code with ruff ---"
	@$(VENV_ACTIVATE) && ruff format src tests scripts

.PHONY: typecheck
typecheck:
	@echo "--- Running mypy type checker ---"
	@$(VVENV_ACTIVATE) && mypy src --strict

# --- Testing ---
.PHONY: test
test:
	@echo "--- Running unit and integration tests with pytest ---"
	@$(VENV_ACTIVATE) && pytest

.PHONY: test-cov
test-cov:
	@echo "--- Running tests with coverage report ---"
	@$(VENV_ACTIVATE) && pytest --cov=src --cov-report term-missing

.PHONY: coverage-report
coverage-report:
	@echo "--- Generating HTML coverage report ---"
	@$(VENV_ACTIVATE) && coverage html
	@echo "--- Report available at htmlcov/index.html ---"
