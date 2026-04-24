.PHONY: help up down logs test lint format

help:
	@echo "NemoClaw SaaS Platform — 常用命令"
	@echo ""
	@echo "  make up            啟動所有服務（Docker Compose）"
	@echo "  make down          停止所有服務"
	@echo "  make logs          查看所有服務日誌"
	@echo "  make test          執行所有服務的 unit test"
	@echo "  make test s=tenant 只執行指定服務的 test（s=sandbox|inference-gw|billing）"
	@echo "  make lint          執行 ruff lint 檢查"
	@echo "  make format        執行 ruff format"

up:
	cp -n .env.example .env 2>/dev/null || true
	docker compose up --build -d
	@echo "✅ 所有服務啟動中，等待 health check..."
	@sleep 3
	docker compose ps

down:
	docker compose down

logs:
	docker compose logs -f

# Unit tests（不需要 Docker，直接用 uv 跑）
test:
ifdef s
	cd services/$(s) && uv run pytest tests/ -v
else
	@for svc in tenant sandbox inference-gw billing; do \
		echo "▶ Testing $$svc..."; \
		cd services/$$svc && uv run pytest tests/ -v && cd ../..; \
	done
endif

lint:
	uv run ruff check .

format:
	uv run ruff format .
