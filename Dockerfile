FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /usr/local/bin/uv
ENV UV_LINK_MODE=copy
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --locked --no-dev
RUN useradd --create-home --uid 1000 agent && mkdir /workspace && chown agent:agent /workspace
ENV PATH="/app/.venv/bin:$PATH"
USER agent
WORKDIR /workspace
ENTRYPOINT ["qiskit-lab"]
CMD ["--help"]
