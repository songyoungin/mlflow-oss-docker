"""수동 트레이싱 예제 (에이전트 / LLM / 도구 호출 시뮬레이션).

@mlflow.trace 데코레이터로 중첩 호출을 span으로 기록한다.
실제 Google ADK / OpenTelemetry 연동은 README의 "OTLP 트레이스 수집" 섹션 참고.
"""

from __future__ import annotations

import os
import time

import mlflow
from mlflow.entities import SpanType

os.environ.setdefault("MLFLOW_TRACKING_USERNAME", "admin")
os.environ.setdefault("MLFLOW_TRACKING_PASSWORD", "adminpassword")

mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5050"))
mlflow.set_experiment("demo-tracing")


@mlflow.trace(span_type=SpanType.TOOL)
def search_tool(query: str) -> str:
    time.sleep(0.1)
    return f"'{query}'에 대한 검색 결과 3건"


@mlflow.trace(span_type=SpanType.LLM, attributes={"model": "demo-llm"})
def llm_call(prompt: str) -> str:
    time.sleep(0.2)
    return f"요약 응답: {prompt[:30]}..."


@mlflow.trace(span_type=SpanType.AGENT)
def agent(question: str) -> str:
    context = search_tool(question)
    return llm_call(f"질문: {question}\n참고 컨텍스트: {context}")


if __name__ == "__main__":
    answer = agent("MLflow 트레이싱이란 무엇인가?")
    print(f"에이전트 응답: {answer}")
    print("UI의 'Traces' 탭에서 span 트리를 확인: http://localhost:5050")
