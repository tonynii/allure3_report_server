FROM node:22-slim AS node-base

FROM python:3.12-slim

# Install uv
RUN pip install uv

# Node.js + allure CLI
COPY --from=node-base /usr/local/lib/node_modules /usr/local/lib/node_modules
COPY --from=node-base /usr/local/bin/node /usr/local/bin/
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
    && npm install -g allure && apt update && apt install -y vim

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY app/ ./app/
COPY alembic.ini ./
COPY alembic/ ./alembic/

RUN mkdir -p /data/allure

EXPOSE 8000

CMD ["sh", "-c", "uv run alembic stamp head 2>/dev/null; uv run alembic upgrade head && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000"]
