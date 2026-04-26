# Auth Setup

이 앱은 `APP_USERNAME`, `APP_PASSWORD`가 설정되어 있으면 로그인 후에만 열립니다.

## Streamlit Community Cloud

앱 설정의 `Secrets`에 아래처럼 넣습니다.

```toml
APP_USERNAME = "your-id"
APP_PASSWORD = "your-password"
APP_MAX_LOGIN_ATTEMPTS = 5
APP_LOCKOUT_MINUTES = 15
```

## 로컬 실행

PowerShell에서 환경변수로 실행할 수 있습니다.

```powershell
$env:APP_USERNAME="your-id"
$env:APP_PASSWORD="your-password"
streamlit run app.py
```

## 동작

- 로그인 전에는 앱 본문이 열리지 않습니다.
- 로그인 후에는 세션 동안 유지됩니다.
- 사이드바에서 `로그아웃`할 수 있습니다.
- 로그인 실패가 지정 횟수를 넘으면 일정 시간 잠깁니다.

## 관리자 조정 항목

- `APP_MAX_LOGIN_ATTEMPTS`: 허용 로그인 실패 횟수
- `APP_LOCKOUT_MINUTES`: 초과 시 잠금 시간(분)
