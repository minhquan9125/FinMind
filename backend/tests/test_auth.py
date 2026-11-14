import pytest
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4
from fastapi.testclient import TestClient

from src.main import app
from src.auth.rate_limiter import login_limiter
from src.auth.service import hash_password, verify_password

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_auth_test(monkeypatch):
    """Ensure rate limiter state is reset and db pool is mocked for unit tests."""
    login_limiter.reset()
    monkeypatch.setattr("src.api.routers.auth.get_pool", lambda: object())
    yield
    login_limiter.reset()


def test_register_success(monkeypatch):
    """Bước 1: Tạo chức năng đăng ký bằng thông tin hợp lệ và lưu mật khẩu đã bảo vệ."""
    created_user = None

    async def fake_create_user(pool, email, full_name, password_hash, default_role_code="RESEARCHER"):
        nonlocal created_user
        created_user = {
            "user_id": uuid4(),
            "email": email,
            "full_name": full_name,
            "password_hash": password_hash,
            "is_active": True,
            "created_at": datetime.now(timezone.utc),
            "roles": [default_role_code],
        }
        return created_user

    monkeypatch.setattr("src.auth.repository.create_user", fake_create_user)

    payload = {
        "email": "analyst.test@finmind.vn",
        "full_name": "Nguyen Minh Quan",
        "password": "StrongPassword!2026",
        "confirm_password": "StrongPassword!2026",
        "accept_terms": True,
    }

    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201

    body = response.json()
    assert body["success"] is True
    data = body["data"]
    assert data["email"] == "analyst.test@finmind.vn"
    assert data["full_name"] == "Nguyen Minh Quan"
    assert data["roles"] == ["RESEARCHER"]
    assert "user_id" in data

    # Kiểm tra mật khẩu không được lưu hoặc trả về ở dạng gốc
    assert "password" not in data
    assert created_user is not None
    assert created_user["password_hash"] != "StrongPassword!2026"
    assert created_user["password_hash"].startswith("$argon2")


@pytest.mark.parametrize(
    "invalid_payload,expected_detail",
    [
        (
            {
                "email": "invalid-email",
                "full_name": "Nguyen Minh Quan",
                "password": "StrongPassword!2026",
                "confirm_password": "StrongPassword!2026",
                "accept_terms": True,
            },
            "Email không hợp lệ",
        ),
        (
            {
                "email": "test@finmind.vn",
                "full_name": "Nguyen Minh Quan",
                "password": "simplepassword",  # Thiếu chữ hoa, số, ký tự đặc biệt
                "confirm_password": "simplepassword",
                "accept_terms": True,
            },
            "Mật khẩu cần có",
        ),
        (
            {
                "email": "test@finmind.vn",
                "full_name": "Nguyen Minh Quan",
                "password": "StrongPassword!2026",
                "confirm_password": "WrongPassword!2026",  # Không khớp
                "accept_terms": True,
            },
            "Mật khẩu xác nhận không khớp",
        ),
        (
            {
                "email": "test@finmind.vn",
                "full_name": "Nguyen Minh Quan",
                "password": "StrongPassword!2026",
                "confirm_password": "StrongPassword!2026",
                "accept_terms": False,  # Chưa đồng ý điều khoản
            },
            "Bạn cần đồng ý với điều khoản",
        ),
    ],
)
def test_register_validation_failures(invalid_payload, expected_detail):
    """Kiểm tra từ chối các trường hợp đăng ký dữ liệu không hợp lệ."""
    response = client.post("/api/v1/auth/register", json=invalid_payload)
    assert response.status_code == 422
    assert any(expected_detail in str(err) for err in response.json().get("detail", []))


def test_register_privilege_escalation_blocked():
    """Bước 3: Xác nhận người dùng không tự cấp quyền cao hơn (chống privilege escalation)."""
    payload_with_roles = {
        "email": "hacker@finmind.vn",
        "full_name": "Intruder User",
        "password": "StrongPassword!2026",
        "confirm_password": "StrongPassword!2026",
        "accept_terms": True,
        "role": "ADMIN",
        "roles": ["ADMIN", "SUPERUSER"],
        "is_admin": True,
    }

    response = client.post("/api/v1/auth/register", json=payload_with_roles)
    # Extra fields are forbidden by Pydantic model_config(extra="forbid")
    assert response.status_code == 422
    errors = response.json().get("detail", [])
    err_types = [e.get("type") for e in errors]
    assert "extra_forbidden" in err_types


def test_login_success(monkeypatch):
    """Bước 2: Đăng nhập thành công với thông tin hợp lệ."""
    user_id = uuid4()
    hashed = hash_password("ValidPassword!2026")

    async def fake_find_user_by_email(pool, email):
        return {
            "user_id": user_id,
            "email": email,
            "full_name": "Nguyen Minh Quan",
            "password_hash": hashed,
            "is_active": True,
        }

    async def fake_get_user_roles(pool, uid):
        return ["RESEARCHER"]

    async def fake_create_session(pool, uid, token_hash, days):
        return None

    async def fake_record_login(pool, uid):
        return None

    monkeypatch.setattr("src.auth.repository.find_user_by_email", fake_find_user_by_email)
    monkeypatch.setattr("src.auth.repository.get_user_roles", fake_get_user_roles)
    monkeypatch.setattr("src.auth.repository.create_session", fake_create_session)
    monkeypatch.setattr("src.auth.repository.record_login", fake_record_login)

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "analyst@finmind.vn", "password": "ValidPassword!2026"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    data = body["data"]
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "Bearer"
    assert data["user"]["roles"] == ["RESEARCHER"]


def test_login_wrong_password_and_timing_safety(monkeypatch):
    """Bước 2: Sai mật khẩu bị từ chối; trả thông báo không tiết lộ dữ liệu nhạy cảm."""
    user_id = uuid4()
    hashed = hash_password("CorrectPassword!2026")

    async def fake_find_user_by_email(pool, email):
        return {
            "user_id": user_id,
            "email": email,
            "full_name": "Nguyen Minh Quan",
            "password_hash": hashed,
            "is_active": True,
        }

    monkeypatch.setattr("src.auth.repository.find_user_by_email", fake_find_user_by_email)

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "analyst@finmind.vn", "password": "WrongPassword!2026"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Email hoặc mật khẩu không đúng."


def test_login_nonexistent_email(monkeypatch):
    """Kiểm tra email không tồn tại trả cùng thông báo 401 (chống user enumeration)."""
    async def fake_find_user_by_email(pool, email):
        return None

    monkeypatch.setattr("src.auth.repository.find_user_by_email", fake_find_user_by_email)

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "unknown@finmind.vn", "password": "AnyPassword!2026"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Email hoặc mật khẩu không đúng."


def test_login_consecutive_failed_attempts_rate_limiting(monkeypatch):
    """Bước 2: Giới hạn thử liên tiếp (Account Lockout sau 5 lần thử sai)."""
    async def fake_find_user_by_email(pool, email):
        return None  # Giả lập thất bại

    monkeypatch.setattr("src.auth.repository.find_user_by_email", fake_find_user_by_email)

    email = "brute.force@finmind.vn"

    # Thử sai 4 lần đầu -> trả 401
    for i in range(4):
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": f"Attempt{i}!2026"},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Email hoặc mật khẩu không đúng."

    # Lần thử thứ 5 -> Đạt ngưỡng giới hạn -> Bị khóa ngay và trả 429
    resp_5 = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Attempt5!2026"},
    )
    assert resp_5.status_code == 429
    assert "tạm khóa" in resp_5.json()["detail"]
    assert "Retry-After" in resp_5.headers

    # Lần thử thứ 6 -> Đang bị khóa -> Bị chặn ngay lập tức từ vòng pre-check (429)
    resp_6 = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "AnyAttempt!2026"},
    )
    assert resp_6.status_code == 429
    assert "Tài khoản tạm thời bị khóa" in resp_6.json()["detail"]


@pytest.mark.parametrize("has_existing_password", [True, False])
def test_forgot_and_reset_password_flow(monkeypatch, has_existing_password):
    """Exercise the reset link and password update without DB or SMTP writes."""
    user_id = uuid4()
    email = "reset.test@finmind.vn"
    original_hash = hash_password("OldPassword!2026") if has_existing_password else None
    account = {"password_hash": original_hash}
    sent_links = []
    replacement = {}

    async def fake_find_user_by_email(pool, requested_email):
        assert requested_email == email
        return {
            "user_id": user_id,
            "email": email,
            "password_hash": account["password_hash"],
            "is_active": True,
        }

    async def fake_find_user_by_id(pool, requested_id):
        assert requested_id == user_id
        return {"user_id": user_id, "password_hash": account["password_hash"], "is_active": True}

    async def fake_replace_password(pool, requested_id, current_hash, new_hash):
        if account["password_hash"] != current_hash:
            return False
        account["password_hash"] = new_hash
        replacement.update(user_id=requested_id, old=current_hash, new=new_hash)
        return True

    monkeypatch.setattr("src.auth.repository.find_user_by_email", fake_find_user_by_email)
    monkeypatch.setattr("src.auth.repository.find_user_by_id", fake_find_user_by_id)
    monkeypatch.setattr("src.auth.repository.replace_password_if_current", fake_replace_password)
    monkeypatch.setattr(
        "src.api.routers.auth.send_reset_email",
        lambda to_email, reset_url: sent_links.append((to_email, reset_url)),
    )

    forgot = client.post("/api/v1/auth/password/forgot", json={"email": email})
    assert forgot.status_code == 202
    assert sent_links[0][0] == email
    token = parse_qs(urlsplit(sent_links[0][1]).fragment)["token"][0]

    reset = client.post(
        "/api/v1/auth/password/reset",
        json={
            "recovery_code": token,
            "new_password": "NewPassword!2026",
            "confirm_password": "NewPassword!2026",
        },
    )
    assert reset.status_code == 204
    assert replacement["user_id"] == user_id
    assert replacement["old"] == original_hash
    assert verify_password("NewPassword!2026", replacement["new"])

    replay = client.post(
        "/api/v1/auth/password/reset",
        json={
            "recovery_code": token,
            "new_password": "AnotherPassword!2026",
            "confirm_password": "AnotherPassword!2026",
        },
    )
    assert replay.status_code == 400


def test_reset_password_rejects_invalid_token():
    response = client.post(
        "/api/v1/auth/password/reset",
        json={
            "recovery_code": "invalid-token-of-sufficient-length",
            "new_password": "NewPassword!2026",
            "confirm_password": "NewPassword!2026",
        },
    )
    assert response.status_code == 400


def test_google_login_tolerates_small_clock_skew(monkeypatch):
    observed = {}
    user_id = uuid4()

    def fake_verify_token(credential, request, audience, clock_skew_in_seconds=0):
        observed["credential"] = credential
        observed["skew"] = clock_skew_in_seconds
        return {"email": "google.test@finmind.vn", "name": "Google Test"}

    async def fake_get_or_create_user(pool, email, full_name):
        return {"user_id": user_id, "email": email, "full_name": full_name, "is_active": True}

    async def fake_get_user_roles(pool, requested_id):
        return ["RESEARCHER"]

    async def fake_create_session(pool, requested_id, token_hash, days):
        return None

    async def fake_record_login(pool, requested_id):
        return None

    monkeypatch.setattr("src.api.routers.auth.id_token.verify_oauth2_token", fake_verify_token)
    monkeypatch.setattr("src.auth.repository.get_or_create_google_user", fake_get_or_create_user)
    monkeypatch.setattr("src.auth.repository.get_user_roles", fake_get_user_roles)
    monkeypatch.setattr("src.auth.repository.create_session", fake_create_session)
    monkeypatch.setattr("src.auth.repository.record_login", fake_record_login)

    response = client.post("/api/v1/auth/google", json={"credential": "test-google-token"})
    assert response.status_code == 200
    assert observed == {"credential": "test-google-token", "skew": 5}


def test_refresh_rotates_token_and_rejects_replay(monkeypatch):
    user_id = uuid4()
    active_hashes = set()
    from src.auth.service import create_refresh_token, hash_refresh_token
    raw, digest = create_refresh_token()
    active_hashes.add(digest)

    async def fake_rotate(pool, old_hash, new_hash, days):
        if old_hash not in active_hashes:
            return None
        active_hashes.remove(old_hash)
        active_hashes.add(new_hash)
        return {"user_id": user_id, "email": "session@finmind.vn", "full_name": "Session User"}

    async def fake_roles(pool, requested_id):
        return ["RESEARCHER"]

    monkeypatch.setattr("src.auth.repository.rotate_session", fake_rotate)
    monkeypatch.setattr("src.auth.repository.get_user_roles", fake_roles)

    first = client.post("/api/v1/auth/refresh", json={"refresh_token": raw})
    assert first.status_code == 200
    new_raw = first.json()["data"]["refresh_token"]
    assert hash_refresh_token(new_raw) in active_hashes

    replay = client.post("/api/v1/auth/refresh", json={"refresh_token": raw})
    assert replay.status_code == 401
    invalid = client.post("/api/v1/auth/refresh", json={"refresh_token": "x" * 40})
    assert invalid.status_code == 401


def test_logout_revokes_refresh_session(monkeypatch):
    revoked = []

    async def fake_revoke(pool, token_hash):
        revoked.append(token_hash)
        return True

    monkeypatch.setattr("src.auth.repository.revoke_session", fake_revoke)
    from src.auth.service import hash_refresh_token
    raw = "a" * 48
    response = client.post("/api/v1/auth/logout", json={"refresh_token": raw})
    assert response.status_code == 204
    assert revoked == [hash_refresh_token(raw)]


def test_refresh_rejects_expired_session(monkeypatch):
    async def expired_session(pool, old_hash, new_hash, days):
        return None

    monkeypatch.setattr("src.auth.repository.rotate_session", expired_session)
    response = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": "e" * 48}
    )
    assert response.status_code == 401
