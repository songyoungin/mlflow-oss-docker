"""basic-auth Admin API 예제: 유저 생성 + experiment(프로젝트) 단위 권한 부여/회수.

"단일 조직 내에서 프로젝트별 접근 권한을 API로 제어"하는 시나리오를 검증한다.

흐름:
  1. 일반 유저(bob) 생성
  2. experiment(team-a-project) 생성
  3. bob에게 READ 권한 부여 → NO_PERMISSIONS로 회수 → READ 재부여

참고(한계): MLflow basic-auth는 유저 단위 권한만 지원하며 팀/그룹 개념이 없다.
"""

from __future__ import annotations

import os

import mlflow
from mlflow.server import get_app_client

TRACKING_URI = os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5050")

# Admin API는 관리자 자격증명으로 인증해야 한다
os.environ.setdefault("MLFLOW_TRACKING_USERNAME", "admin")
os.environ.setdefault("MLFLOW_TRACKING_PASSWORD", "adminpassword")

mlflow.set_tracking_uri(TRACKING_URI)


def main() -> None:
    auth_client = get_app_client("basic-auth", tracking_uri=TRACKING_URI)

    # 1. 유저 생성 (이미 존재하면 건너뜀)
    try:
        auth_client.create_user(username="bob", password="bob-password-1")
        print("유저 생성: bob")
    except Exception as exc:  # 이미 존재 등
        print(f"유저 생성 건너뜀: {exc}")

    # 2. experiment(프로젝트) 생성
    client = mlflow.MlflowClient()
    exp_name = "team-a-project"
    existing = client.get_experiment_by_name(exp_name)
    experiment_id = existing.experiment_id if existing else client.create_experiment(exp_name)
    print(f"experiment: {exp_name} (id={experiment_id})")

    # 3. READ 권한 부여
    auth_client.create_experiment_permission(
        experiment_id=experiment_id, username="bob", permission="READ"
    )
    print("bob → READ 권한 부여")

    # 권한 회수 (열람 차단)
    auth_client.update_experiment_permission(
        experiment_id=experiment_id, username="bob", permission="NO_PERMISSIONS"
    )
    print("bob → NO_PERMISSIONS (열람 차단)")

    # READ 재부여
    auth_client.update_experiment_permission(
        experiment_id=experiment_id, username="bob", permission="READ"
    )
    print("bob → READ 권한 재부여")

    print("\nbob / bob-password-1 로 로그인해 권한 변화를 확인: http://localhost:5050")


if __name__ == "__main__":
    main()
