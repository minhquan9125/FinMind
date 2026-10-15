import pytest
from datetime import datetime, timezone
from uuid import uuid4
from fastapi.testclient import TestClient

from src.main import app
from src.auth.rate_limiter import login_limiter
from src.auth.service import hash_password

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
