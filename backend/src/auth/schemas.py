import re
import string
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str = Field(min_length=2, max_length=255)
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(max_length=128)
    accept_terms: bool

    @field_validator("full_name")
    @classmethod
    def clean_full_name(cls, value: str) -> str:
        value = " ".join(value.split())
        if len(value) < 2:
            raise ValueError("Họ tên phải có ít nhất 2 ký tự.")
        return value

    @field_validator("email")
    @classmethod
    def clean_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            raise ValueError("Email không hợp lệ.")
        return value

    @field_validator("password")
    @classmethod
    def check_password_strength(cls, value: str) -> str:
        if any(char.isspace() for char in value):
            raise ValueError("Mật khẩu không được chứa khoảng trắng.")
        if not any(char.isupper() for char in value):
            raise ValueError("Mật khẩu cần có ít nhất một chữ in hoa.")
        if not any(char.islower() for char in value):
            raise ValueError("Mật khẩu cần có ít nhất một chữ thường.")
        if not any(char.isdigit() for char in value):
            raise ValueError("Mật khẩu cần có ít nhất một chữ số.")
        if not any(char in string.punctuation for char in value):
            raise ValueError("Mật khẩu cần có ít nhất một ký tự đặc biệt.")
        return value

    @field_validator("accept_terms")
    @classmethod
    def must_accept_terms(cls, value: bool) -> bool:
        if not value:
            raise ValueError("Bạn cần đồng ý với điều khoản sử dụng.")
        return value

    @model_validator(mode="after")
    def passwords_must_match(self):
        if self.password != self.confirm_password:
            raise ValueError("Mật khẩu xác nhận không khớp.")
        return self
        
class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str
    password: str

    @field_validator("email")
    @classmethod
    def clean_login_email(cls, value: str) -> str:
        return value.strip().lower()

class GoogleLoginRequest(BaseModel):
    credential: str


class ForgotPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=255)

    @field_validator("email")
    @classmethod
    def clean_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            raise ValueError("Email không hợp lệ.")
        return value

class ResetPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recovery_code: str = Field(min_length=20, max_length=4096)
    new_password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(max_length=128)

    @field_validator("new_password")
    @classmethod
    def check_password_strength(cls, value: str) -> str:
        if (
            any(char.isspace() for char in value)
            or not any(char.isupper() for char in value)
            or not any(char.islower() for char in value)
            or not any(char.isdigit() for char in value)
            or not any(char in string.punctuation for char in value)
        ):
            raise ValueError(
                "Mật khẩu cần có chữ hoa, chữ thường, số và ký tự đặc biệt; "
                "không chứa khoảng trắng."
            )
        return value

    @model_validator(mode="after")
    def passwords_must_match(self):
        if self.new_password != self.confirm_password:
            raise ValueError("Mật khẩu xác nhận không khớp.")
        return self
