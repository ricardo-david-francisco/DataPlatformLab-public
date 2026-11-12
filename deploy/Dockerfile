# The pipeline as an image: dlt + dbt + the migration tools, run by ./run.sh. Build from the repo root:
#   docker build -f deploy/Dockerfile -t dataplatformlab:latest .
FROM python:3.12-slim AS build
WORKDIR /build
COPY requirements.txt .
RUN python -m venv /venv && /venv/bin/pip install --no-cache-dir -r requirements.txt

FROM python:3.12-slim
RUN useradd --create-home --uid 10001 dpl
COPY --from=build /venv /venv
WORKDIR /app
COPY --chown=dpl:dpl . .
USER 10001
ENV PATH=/venv/bin:$PATH DPL_VENV=/venv DPL_WAREHOUSE=/tmp/warehouse/lab.duckdb DPL_DLT_DIR=/tmp/dlt
ENTRYPOINT ["./run.sh"]
CMD ["--offline"]
