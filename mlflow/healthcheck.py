"""컨테이너 healthcheck.

basic-auth가 /health까지 보호하므로 무인증 요청은 403을 받는다.
HTTP 응답(403 포함)이 오면 서버는 살아있는 것으로 간주하고, 연결 자체가
실패할 때만 unhealthy로 처리한다.
"""

import sys
import urllib.error
import urllib.request

try:
    urllib.request.urlopen("http://localhost:5000/health", timeout=3)
except urllib.error.HTTPError:
    # 401/403 등 HTTP 응답이 왔다 = 서버 기동됨
    pass
except Exception:
    sys.exit(1)

sys.exit(0)
