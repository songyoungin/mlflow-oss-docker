"""기본 실험 로깅 예제.

experiment를 만들고 파라미터/메트릭/아티팩트를 기록한다.
basic-auth가 켜져 있으므로 관리자 자격증명이 필요하다(기본값: admin / password).
아티팩트는 서버가 MinIO로 프록시하므로 클라이언트에 S3 자격증명이 필요 없다.
"""

from __future__ import annotations

import os
import random

import mlflow

# basic-auth 자격증명 (없으면 기본 관리자 계정 사용)
os.environ.setdefault("MLFLOW_TRACKING_USERNAME", "admin")
os.environ.setdefault("MLFLOW_TRACKING_PASSWORD", "adminpassword")

mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5050"))


def main() -> None:
    mlflow.set_experiment("demo-experiment")
    with mlflow.start_run(run_name="baseline") as run:
        mlflow.log_param("learning_rate", 0.01)
        mlflow.log_param("epochs", 10)
        for epoch in range(10):
            mlflow.log_metric("loss", 1.0 / (epoch + 1), step=epoch)
            mlflow.log_metric("accuracy", random.uniform(0.7, 0.99), step=epoch)
        mlflow.log_text("아티팩트 저장 테스트(MinIO 프록시)", "notes.txt")
        print(f"run 생성 완료: {run.info.run_id}")
    print("UI에서 확인: http://localhost:5050")


if __name__ == "__main__":
    main()
