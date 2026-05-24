"""실제 Google ADK 멀티에이전트 + OpenAI(LiteLLM) → MLflow OTLP 트레이싱.

오케스트레이터가 두 서브에이전트(research_agent, math_agent)를 AgentTool로 호출하고,
ADK가 생성한 OpenTelemetry span을 MLflow의 /v1/traces 엔드포인트로 export한다.

필요 환경변수:
  OPENAI_API_KEY               OpenAI 키
  OTEL_EXPORTER_OTLP_ENDPOINT  예: http://localhost:5050
  OTEL_EXPORTER_OTLP_HEADERS   예: Authorization=Basic <b64>,x-mlflow-experiment-id=<id>

실행: .venv/bin/python examples/adk_agent.py
"""

from __future__ import annotations

import ast
import asyncio
import operator

from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools.agent_tool import AgentTool
from google.genai import types
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

# 1) OpenTelemetry tracer provider → MLflow OTLP exporter (env에서 endpoint/headers 읽음)
_provider = TracerProvider()
_provider.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter()))
trace.set_tracer_provider(_provider)

MODEL = "openai/gpt-4o-mini"

_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
}


def _safe_eval(node: ast.AST) -> float:
    """산술 식만 허용하는 안전 평가기 (eval 미사용)."""
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_safe_eval(node.operand))
    raise ValueError("지원하지 않는 식")


def web_search(query: str) -> str:
    """주어진 질의에 대한 웹 검색 결과를 반환한다(데모용 스텁)."""
    return f"[검색결과] '{query}' 관련 자료 3건 요약"


def calculator(expression: str) -> str:
    """간단한 산술식을 계산한다. 예: '21*2'."""
    try:
        return str(_safe_eval(ast.parse(expression, mode="eval").body))
    except Exception as exc:  # noqa: BLE001 - 데모
        return f"계산오류: {exc}"


research_agent = LlmAgent(
    name="research_agent",
    model=LiteLlm(model=MODEL),
    instruction="너는 리서치 담당이다. web_search 도구로 자료를 찾아 간결히 요약하라.",
    tools=[web_search],
)
math_agent = LlmAgent(
    name="math_agent",
    model=LiteLlm(model=MODEL),
    instruction="너는 계산 담당이다. calculator 도구로 산술을 수행하라.",
    tools=[calculator],
)
orchestrator = LlmAgent(
    name="orchestrator",
    model=LiteLlm(model=MODEL),
    instruction=(
        "너는 조정자다. 사용자 질문을 분해해 research_agent와 math_agent를 모두 호출하고, "
        "두 결과를 종합해 최종 답을 한국어로 작성하라."
    ),
    tools=[AgentTool(agent=research_agent), AgentTool(agent=math_agent)],
)


async def main() -> None:
    session_service = InMemorySessionService()
    await session_service.create_session(app_name="adk_demo", user_id="u1", session_id="s1")
    runner = Runner(app_name="adk_demo", agent=orchestrator, session_service=session_service)

    msg = types.Content(
        role="user",
        parts=[types.Part(text="MLflow의 장점을 한 줄로 알려주고, 21 곱하기 2도 계산해줘.")],
    )

    final = None
    async for event in runner.run_async(user_id="u1", session_id="s1", new_message=msg):
        if event.is_final_response() and event.content:
            final = "".join(p.text or "" for p in event.content.parts)

    print("최종 응답:", final)
    _provider.force_flush()


if __name__ == "__main__":
    asyncio.run(main())
