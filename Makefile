# Humbert dev helpers. `make dev` is the one you want while building the UI.

# Run the backend (API on :8000) and the Vite dev server (HMR on :5173) together.
# Open http://localhost:5173 — that's the one with hot reload; :8000 serves the
# last built bundle. Ctrl-C stops both.
.PHONY: dev
dev:
	@echo "Backend  → http://localhost:8000  (API)"
	@echo "Frontend → http://localhost:5173  (open this — hot reload)"
	@trap 'kill 0' EXIT; \
	  (cd apps/api && uv run humbert start --no-browser) & \
	  (cd apps/web && npm run dev) & \
	  wait

# The same checks CI runs: lint, format, types, tests, and the frontend build.
.PHONY: gates
gates:
	cd apps/api && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest
	cd apps/web && npm run build

# Build the frontend once so `humbert start` has something to serve.
.PHONY: build-web
build-web:
	cd apps/web && npm run build
