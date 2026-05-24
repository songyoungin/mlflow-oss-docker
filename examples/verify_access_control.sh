#!/usr/bin/env bash
#
# MLflow basic-auth 접근제어 / 트레이스 격리 재현 검증 스크립트.
#
# 검증 항목:
#   1. admin이 프로젝트(experiment) 생성 + 유저 발급 + 프로젝트별 권한 부여
#   2. 권한 매트릭스: agent-svc(EDIT)/bob(READ)의 allow/deny가 기대대로인지
#   3. 유저 발급이 admin 전용인지 (무인증/비관리자 차단)
#   4. ⚠️ 트레이스 검색 엔드포인트의 권한 누수(프로젝트별 트레이스 격리 미보장)
#
# 사전조건: `docker compose up -d` 후 mlflow-server 컨테이너가 동작 중.
# 실행:     bash examples/verify_access_control.sh
#
set -uo pipefail

BASE="${MLFLOW_BASE_URL:-http://localhost:5050}"
ADMIN_USER="${MLFLOW_ADMIN_USERNAME:-admin}"
ADMIN_PASS="${MLFLOW_ADMIN_PASSWORD:-adminpassword}"
ADMIN="${ADMIN_USER}:${ADMIN_PASS}"
CONTAINER="${MLFLOW_CONTAINER:-mlflow-server}"
H="Content-Type: application/json"

AGENT="agent-svc:agentsvcpassword"
BOB="bob:bobuserpassword"

pass=0; fail=0; warn=0
check() { # check <label> <expected> <actual>
  if [ "$2" = "$3" ]; then echo "  ✅ $1 ($3)"; pass=$((pass + 1))
  else echo "  ❌ $1 (기대 $2, 실제 $3)"; fail=$((fail + 1)); fi
}
code() { curl -s -o /dev/null -w '%{http_code}' "$@"; } # status code만 반환

# ── 0. 셋업 (idempotent): 프로젝트/유저/권한 — 컨테이너 안 admin 클라이언트로 처리 ──
echo "== 0. 셋업 (프로젝트·유저·권한) =="
IDS=$(docker exec \
  -e MLFLOW_TRACKING_USERNAME="$ADMIN_USER" -e MLFLOW_TRACKING_PASSWORD="$ADMIN_PASS" \
  "$CONTAINER" python -c '
import mlflow
from mlflow.server import get_app_client
mlflow.set_tracking_uri("http://localhost:5000")
c = mlflow.MlflowClient()
def ensure_exp(n):
    e = c.get_experiment_by_name(n)
    return e.experiment_id if e else c.create_experiment(n)
alpha, beta = ensure_exp("team-alpha"), ensure_exp("team-beta")
ac = get_app_client("basic-auth", "http://localhost:5000")
def ensure_user(u, p):
    try: ac.create_user(u, p)
    except Exception: pass
ensure_user("agent-svc", "agentsvcpassword")
ensure_user("bob", "bobuserpassword")
def ensure_perm(e, u, perm):
    try: ac.create_experiment_permission(e, u, perm)
    except Exception: ac.update_experiment_permission(e, u, perm)
ensure_perm(alpha, "agent-svc", "EDIT")
ensure_perm(alpha, "bob", "READ")
print(alpha, beta)
' 2>/dev/null | tail -1)
ALPHA=$(echo "$IDS" | awk '{print $1}')
BETA=$(echo "$IDS" | awk '{print $2}')
if [ -z "$ALPHA" ] || [ -z "$BETA" ]; then
  echo "  ❌ 셋업 실패 — mlflow-server 컨테이너/자격증명을 확인하세요."; exit 1
fi
echo "  team-alpha=$ALPHA, team-beta=$BETA | agent-svc(EDIT@alpha), bob(READ@alpha)"

# ── 1. agent-svc(고유 로그인)가 team-alpha에 트레이스 기록 ──
echo "== 1. agent-svc가 team-alpha에 트레이스 기록 =="
if docker exec -e MLFLOW_TRACKING_USERNAME=agent-svc -e MLFLOW_TRACKING_PASSWORD=agentsvcpassword \
  "$CONTAINER" python -c '
import mlflow
from mlflow.entities import SpanType
mlflow.set_tracking_uri("http://localhost:5000")
mlflow.set_experiment("team-alpha")
@mlflow.trace(span_type=SpanType.AGENT, name="orchestrator")
def f(): return "ok"
f()
' >/dev/null 2>&1; then echo "  ✅ 기록 완료"; pass=$((pass + 1)); else echo "  ❌ 기록 실패"; fail=$((fail + 1)); fi

# ── 2. 권한 매트릭스 ──
# 변수가 들어가는 JSON 본문은 미리 변수로 만든다(이스케이프 JSON을 "$(...)" 안에 직접 넣으면 깨짐).
echo "== 2. 권한 매트릭스 (status code) =="
run_body=$(printf '{"experiment_id":"%s","start_time":0}' "$ALPHA")
check "agent-svc → team-beta GET = 403 (미부여)"    403 "$(code -u "$AGENT" "$BASE/api/2.0/mlflow/experiments/get?experiment_id=$BETA")"
check "bob → team-alpha GET = 200 (READ 부여됨)"     200 "$(code -u "$BOB" "$BASE/api/2.0/mlflow/experiments/get?experiment_id=$ALPHA")"
check "bob → team-alpha 쓰기(run 생성) = 403 (READ 전용)" 403 "$(code -u "$BOB" -H "$H" -X POST "$BASE/api/2.0/mlflow/runs/create" -d "$run_body")"
check "bob → team-beta GET = 403 (미부여)"            403 "$(code -u "$BOB" "$BASE/api/2.0/mlflow/experiments/get?experiment_id=$BETA")"

# ── 3. 유저 발급은 admin 전용 ──
echo "== 3. 유저 발급 권한 (admin 전용) =="
UNIQ="admintest_$$"
admin_body=$(printf '{"username":"%s","password":"admintestpass12"}' "$UNIQ")
check "무인증 users/create = 401"        401 "$(code -H "$H" -X POST "$BASE/api/2.0/mlflow/users/create" -d '{"username":"anon_x","password":"anonpassword12"}')"
check "bob(비관리자) users/create = 403" 403 "$(code -u "$BOB" -H "$H" -X POST "$BASE/api/2.0/mlflow/users/create" -d '{"username":"bobmade_x","password":"bobmadepass12"}')"
check "admin users/create = 200"         200 "$(code -u "$ADMIN" -H "$H" -X POST "$BASE/api/2.0/mlflow/users/create" -d "$admin_body")"
curl -s -u "$ADMIN" -H "$H" -X POST "$BASE/api/2.0/mlflow/users/delete" -d "{\"username\":\"$UNIQ\"}" >/dev/null 2>&1 # cleanup

# ── 4. ⚠️ 트레이스 격리 누수 ──
echo "== 4. 트레이스 격리 누수 검증 =="
docker exec -e MLFLOW_TRACKING_USERNAME="$ADMIN_USER" -e MLFLOW_TRACKING_PASSWORD="$ADMIN_PASS" \
  "$CONTAINER" python -c '
import mlflow
from mlflow.entities import SpanType
mlflow.set_tracking_uri("http://localhost:5000")
mlflow.set_experiment("team-beta")
@mlflow.trace(span_type=SpanType.AGENT, name="beta_secret")
def f(): return "secret"
f()
' >/dev/null 2>&1
sleep 2
search_body=$(printf '{"locations":[{"type":"MLFLOW_EXPERIMENT","mlflow_experiment":{"experiment_id":"%s"}}],"max_results":5}' "$BETA")
beta_meta=$(code -u "$BOB" "$BASE/api/2.0/mlflow/experiments/get?experiment_id=$BETA")
beta_trace=$(code -u "$BOB" -H "$H" -X POST "$BASE/api/3.0/mlflow/traces/search" -d "$search_body")
echo "  bob → team-beta 메타데이터 GET : $beta_meta (403=보호)"
echo "  bob → team-beta traces/search  : $beta_trace (200=누수)"
if [ "$beta_meta" = "403" ] && [ "$beta_trace" = "200" ]; then
  echo "  ⚠️  확인됨: 메타데이터는 막히나 트레이스 검색은 권한을 무시 → 트레이스 격리 누수"
  warn=$((warn + 1))
fi

echo ""
echo "================ 결과: PASS=$pass FAIL=$fail WARN(누수)=$warn ================"
if [ "$fail" -eq 0 ]; then
  echo "권한 부여/격리(메타데이터)·유저 발급 모델은 기대대로 동작."
  echo "단, 트레이스 검색 엔드포인트 격리 누수(WARN)는 멀티팀 트레이스 격리에 부적합."
else
  echo "실패 항목이 있습니다. 위 ❌ 를 확인하세요."
fi
