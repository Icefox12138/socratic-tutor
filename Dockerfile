# sidecar 0.2.1: audit-only sandbox, cross-platform
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SOCRATIC_BGE=0 \
    SOCRATIC_TRANSLATE=glossary \
    SOCRATIC_ROOT=/books \
    SOCRATIC_LIBRARY=/books \
    SOCRATIC_DATA=/data \
    SOCRATIC_DB=/data/search.db \
    SOCRATIC_PUBLIC_DB=/data/public.db \
    SOCRATIC_STATE_DB=/data/state.db \
    SOCRATIC_CACHE=/data/cache

WORKDIR /app

COPY sidecar /app

RUN pip install --no-cache-dir \
      fastapi>=0.110 \
      uvicorn>=0.29 \
      pypdfium2>=4.30 \
      pillow>=10.0 \
      sympy>=1.13 \
      scipy>=1.11 \
      pint>=0.23 \
      control>=0.10 \
      simplemma>=2.0 \
      classics-index>=0.1

EXPOSE 8765

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8765"]
