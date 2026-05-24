"""프롬프트 레지스트리 버저닝 예제.

프롬프트를 등록하면 버전이 자동 증가하고, alias로 특정 버전을 가리킬 수 있다.
"""

from __future__ import annotations

import os

import mlflow

os.environ.setdefault("MLFLOW_TRACKING_USERNAME", "admin")
os.environ.setdefault("MLFLOW_TRACKING_PASSWORD", "password")

mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000"))

PROMPT_NAME = "summarization-prompt"


def main() -> None:
    # v1 등록
    v1 = mlflow.genai.register_prompt(
        name=PROMPT_NAME,
        template="다음 내용을 {{ num_sentences }}문장으로 요약하라:\n\n{{ content }}",
        commit_message="초기 버전",
    )
    print(f"등록: {v1.name} (version {v1.version})")

    # v2 등록 (템플릿 수정 → 새 버전 생성)
    v2 = mlflow.genai.register_prompt(
        name=PROMPT_NAME,
        template="아래 내용을 {{ num_sentences }}문장으로, 핵심만 요약하라:\n\n{{ content }}",
        commit_message="핵심 강조 문구 추가",
    )
    print(f"등록: {v2.name} (version {v2.version})")

    # production alias를 최신 버전(v2)에 지정
    mlflow.genai.set_prompt_alias(PROMPT_NAME, alias="production", version=v2.version)
    print(f"alias 'production' → version {v2.version}")

    # alias로 로드 후 변수 치환
    prod = mlflow.genai.load_prompt(f"prompts:/{PROMPT_NAME}@production")
    rendered = prod.format(num_sentences=3, content="샘플 텍스트입니다.")
    print("\n[production 프롬프트 렌더링 결과]")
    print(rendered)
    print("\nUI의 'Prompts' 탭에서 버전 히스토리/diff를 확인: http://localhost:5000")


if __name__ == "__main__":
    main()
