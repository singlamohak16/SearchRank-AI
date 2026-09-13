FROM python:3.12-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build
COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m pip wheel --wheel-dir /wheels torch --index-url https://download.pytorch.org/whl/cpu \
    && python -m pip wheel --wheel-dir /wheels --find-links /wheels .

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/home/searchrank/.cache/huggingface

RUN groupadd --system searchrank \
    && useradd --system --gid searchrank --create-home searchrank \
    && mkdir -p /home/searchrank/.cache/huggingface \
    && chown -R searchrank:searchrank /home/searchrank

WORKDIR /app
COPY --from=builder /wheels /wheels
RUN python -m pip install --no-index --find-links /wheels searchrank-ai \
    && rm -rf /wheels
COPY --chown=searchrank:searchrank src/searchrank_ai/streamlit_app.py /app/streamlit_app.py

USER searchrank
EXPOSE 8000 8501

CMD ["python", "-m", "uvicorn", "searchrank_ai.api:app", "--host", "0.0.0.0", "--port", "8000"]
