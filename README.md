# mlflow-oss-docker

MLflow OSS(오픈소스)를 **docker compose**로 띄워 핸즈온 테스트하기 위한 레포입니다.
**PostgreSQL(백엔드 스토어) + MinIO(S3 호환 아티팩트 스토어) + basic-auth 플러그인** 구성으로,
운영 환경과 유사한 형태에서 트레이싱·프롬프트 레지스트리·접근 제어를 직접 검증할 수 있습니다.

> **배경**: Langfuse를 대체할 self-hosted OSS 후보로 MLflow를 평가하기 위한 환경입니다.
> 평가 관점의 한계는 맨 아래 [평가 메모](#평가-메모-langfuse-대체-관점)를 참고하세요.

## 구성

```
┌──────────────┐      ┌──────────────────┐      ┌──────────────┐
│  클라이언트   │─────▶│  MLflow Server   │─────▶│  PostgreSQL   │  (실험/메타데이터/프롬프트/권한)
│ (examples/*) │      │  :5000 (basic-   │      └──────────────┘
└──────────────┘      │   auth)          │      ┌──────────────┐
                      │                  │─────▶│    MinIO      │  (아티팩트, S3 프록시)
                      └──────────────────┘      │  :9000/:9001  │
                                                └──────────────┘
```

| 서비스 | 역할 | 포트 |
|--------|------|------|
| `mlflow` | Tracking Server (basic-auth 활성) | 호스트 `5050` → 컨테이너 `5000` |
| `postgres` | 백엔드 스토어 | (내부) |
| `minio` | 아티팩트 스토어 (S3 API / 콘솔) | `9000` / `9001` |
| `minio-init` | `mlflow` 버킷 생성 후 종료 | - |

- MLflow 버전: **3.12.0** (OTLP `/v1/traces` 수집 지원 ≥ 3.6)
- 아티팩트는 서버가 프록시(`--artifacts-destination`)하므로 클라이언트에 S3 자격증명이 필요 없습니다.

## 빠른 시작

```bash
# 1. 환경변수 준비
cp .env.example .env

# 2. 기동 (최초 1회는 이미지 빌드)
docker compose up -d --build

# 3. 상태 확인 (mlflow가 healthy가 될 때까지 대기)
docker compose ps

# 4. 접속
#   - MLflow UI:    http://localhost:5050   (admin / adminpassword)
#   - MinIO 콘솔:    http://localhost:9001   (minioadmin / minioadmin)
```

기본 관리자 계정은 `mlflow/basic_auth.ini`의 `admin / adminpassword`입니다(운영 시 반드시 변경).

## 핸즈온 시나리오

호스트에 클라이언트 의존성을 설치한 뒤 예제를 실행합니다.

```bash
# (권장) uv
uv venv && uv pip install -r examples/requirements.txt
# 또는
pip install -r examples/requirements.txt
```

### 1. 실험 로깅 + 아티팩트
```bash
python examples/log_run.py
```
파라미터/메트릭/아티팩트(MinIO 프록시 저장)를 기록합니다. UI의 *Experiments* 탭에서 확인.

### 2. 트레이싱 (에이전트/LLM/도구 호출)
```bash
python examples/trace_demo.py
```
`@mlflow.trace`로 중첩 span을 기록합니다. UI의 *Traces* 탭에서 span 트리를 확인.

### 3. 프롬프트 레지스트리 버저닝
```bash
python examples/prompt_registry.py
```
프롬프트를 v1→v2로 등록하고 `production` alias를 지정합니다. UI의 *Prompts* 탭에서 버전/diff 확인.

### 4. 접근 제어 Admin API (요구사항 핵심 검증)
```bash
python examples/auth_admin.py
```
유저 생성 → experiment 생성 → 해당 유저에게 **READ 권한 부여/회수/재부여**를 API로 수행합니다.
`bob / bob-password-1`로 로그인해 권한 변화를 확인하세요. (MLflow 3.x는 비밀번호 12자 초과를 요구)

## OTLP 트레이스 수집 (Google ADK / OpenTelemetry)

MLflow 서버는 `/v1/traces` OTLP 엔드포인트를 노출합니다. ADK 등 OpenTelemetry 계측 앱에서
아래 환경변수로 트레이스를 직접 전송할 수 있습니다.

```bash
export OTEL_EXPORTER_OTLP_TRACES_ENDPOINT="http://localhost:5050/v1/traces"
export OTEL_EXPORTER_OTLP_TRACES_PROTOCOL="http/protobuf"
# basic-auth 사용 시 Authorization 헤더 필요 (값은 즉석 생성)
export OTEL_EXPORTER_OTLP_TRACES_HEADERS="Authorization=Basic $(printf 'admin:adminpassword' | base64)"
```

> Google ADK는 OpenTelemetry 네이티브이므로 위 OTLP 엔드포인트로 span이 수집됩니다.
> A2A 프로토콜은 MLflow 전용 통합은 없으며, W3C trace context 전파(OTel) 경유로 동작합니다.

## 정리

```bash
docker compose down        # 컨테이너 중지/삭제
docker compose down -v     # 볼륨(데이터)까지 삭제
```

## 평가 메모 (Langfuse 대체 관점)

실제로 스택을 띄워 검증한 결과(`admin`/`agent-svc`/`bob` 신원으로 직접 접근):

| 요구사항 | MLflow OSS | 검증 결과 |
|----------|-----------|-----------|
| 트레이싱 (OTel / ADK) | ✅ | subagent 중첩 포함 span 트리 정상 기록 (orchestrator→subagent→tool/LLM) |
| 프롬프트 버전 관리 | ✅ | register/alias 동작 |
| 프로젝트(experiment)별 **유저 로그인 + 권한** | ✅ | agent-svc=EDIT(쓰기), bob=READ(읽기) 정상. 미부여 프로젝트는 메타데이터 403 |
| 팀/그룹 | ❌ | 유저 단위 권한만 |
| 조직 생성 Admin API | ❌ | 없음 (experiment≈프로젝트) |
| 멤버 초대 플로우 / SSO | ❌ | 기본 없음 (third-party 플러그인 필요) |

### ⚠️ 중대한 한계: 트레이스 접근 제어 누수 (검증으로 확인)

basic-auth는 **experiment 메타데이터(GET)는 권한 체크하지만, v3 트레이스 검색
엔드포인트(`/api/3.0/mlflow/traces/search`)는 권한 체크를 하지 않는다.**
실측 결과, 권한이 없는(GET 시 403) 프로젝트의 트레이스를 인증된 다른 유저가 그대로 읽혔다.

| bob의 team-beta(미부여) 접근 | 결과 |
|---|---|
| `GET experiment` | **403** (보호됨) |
| `POST /api/3.0/mlflow/traces/search` | **200, 트레이스 노출** (누수) |

→ 트레이싱이 핵심 용도인데 **프로젝트별 트레이스 열람 격리가 보장되지 않으므로**,
멀티팀 트레이스 격리가 필요하면 MLflow OSS basic-auth는 부적합하다.

### 결론
**단일 신뢰 팀**이 프로젝트별로 run/모델 권한을 나누는 정도면 OSS로 충분하다.
하지만 **서로 트레이스를 못 보게 격리**하거나 팀/조직/초대/SSO가 필요하면,
Databricks 매니지드 또는 (트레이스 격리가 동작하는) 다른 도구가 필요하다.

### 핸즈온 중 발견·수정한 운영 이슈
- basic-auth는 `MLFLOW_FLASK_SERVER_SECRET_KEY`(CSRF용)가 **필수** — 없으면 서버 크래시
- MLflow 3.x는 비밀번호 **12자 초과** 강제 (admin/유저 모두)
- macOS는 호스트 `5000`을 AirPlay Receiver가 점유 → 호스트 포트 `5050` 사용
- basic-auth 환경에서 healthcheck는 `/health`도 인증 영향 → 전용 스크립트로 처리
