# MLflow Tracking Server 이미지
# - mlflow[auth]: basic-auth 플러그인 의존성 포함
# - psycopg2-binary: PostgreSQL 백엔드 스토어 드라이버
# - boto3: MinIO(S3 호환) 아티팩트 스토어 접근
FROM python:3.12-slim

ARG MLFLOW_VERSION=3.12.0

RUN pip install --no-cache-dir \
    "mlflow[auth]==${MLFLOW_VERSION}" \
    "psycopg2-binary" \
    "boto3"

# 인증 DB(sqlite)가 저장될 위치
RUN mkdir -p /mlflow-auth

# 컨테이너 healthcheck 스크립트
COPY healthcheck.py /healthcheck.py

WORKDIR /mlflow

EXPOSE 5000
