from typing import Literal
import re

from pydantic import BaseModel, Field, field_validator

class LoginInput(BaseModel):
    email: str
    password: str


class ForgotPasswordInput(BaseModel):
    email: str = Field(max_length=254)


class ResetPasswordInput(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def strong_password(cls, value: str) -> str:
        if not re.search(r"[A-Za-z]", value) or not re.search(r"\d", value):
            raise ValueError("Password must contain letters and numbers")
        return value


INDIA_STATE_CODES = {
    "AP", "AR", "AS", "BR", "CG", "GA", "GJ", "HR", "HP", "JH", "KA", "KL", "MP", "MH", "MN", "ML", "MZ", "NL",
    "OD", "PB", "RJ", "SK", "TN", "TS", "TR", "UP", "UT", "WB", "AN", "CH", "DN", "DL", "JK", "LA", "LD", "PY",
}


class SignupInput(BaseModel):
    owner_name: str = Field(min_length=2, max_length=120)
    restaurant_name: str = Field(min_length=2, max_length=160)
    email: str = Field(max_length=254)
    mobile: str
    password: str = Field(min_length=8, max_length=128)
    address_line: str = Field(min_length=5, max_length=300)
    city: str = Field(min_length=2, max_length=80)
    state_code: str
    pincode: str
    gstin: str | None = None
    plan_name: str = "RESTOIQ_POS"
    billing_cycle: Literal["monthly", "yearly"] = "monthly"

    @field_validator("owner_name", "restaurant_name", "address_line", "city")
    @classmethod
    def strip_text(cls, value: str) -> str:
        value = " ".join(value.split())
        if len(value) < 2:
            raise ValueError("Value is too short")
        return value

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            raise ValueError("Enter a valid email address")
        return value

    @field_validator("mobile")
    @classmethod
    def valid_mobile(cls, value: str) -> str:
        digits = re.sub(r"[\s-]", "", value)
        digits = re.sub(r"^(\+91|0)", "", digits)
        if not re.fullmatch(r"[6-9]\d{9}", digits):
            raise ValueError("Enter a valid 10-digit Indian mobile number")
        return digits

    @field_validator("password")
    @classmethod
    def strong_password(cls, value: str) -> str:
        if not re.search(r"[A-Za-z]", value) or not re.search(r"\d", value):
            raise ValueError("Password must contain letters and numbers")
        return value

    @field_validator("state_code")
    @classmethod
    def valid_state(cls, value: str) -> str:
        value = value.strip().upper()
        if value not in INDIA_STATE_CODES:
            raise ValueError("Select a valid state")
        return value

    @field_validator("pincode")
    @classmethod
    def valid_pincode(cls, value: str) -> str:
        value = value.strip()
        if not re.fullmatch(r"[1-9]\d{5}", value):
            raise ValueError("Enter a valid 6-digit pincode")
        return value

    @field_validator("gstin")
    @classmethod
    def valid_gstin(cls, value: str | None) -> str | None:
        if not value or not value.strip():
            return None
        value = value.strip().upper()
        if not re.fullmatch(r"\d{2}[A-Z]{5}\d{4}[A-Z][A-Z\d]Z[A-Z\d]", value):
            raise ValueError("Enter a valid 15-character GSTIN")
        return value
