FROM continuumio/miniconda3:latest AS builder
WORKDIR /app
COPY environment.yml ./
RUN conda env create -f environment.yml && conda clean -afy

FROM continuumio/miniconda3:latest AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY --from=builder /opt/conda/envs/fleet-telemetry /opt/conda/envs/fleet-telemetry
ENV PATH=/opt/conda/envs/fleet-telemetry/bin:$PATH
COPY pyproject.toml alembic.ini ./
COPY app ./app
COPY alembic ./alembic
COPY scripts ./scripts
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && python -m scripts.seed && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
