import pytest
from pydantic import ValidationError
from app.models import AdminLogin, SignupRequest, EnrollResponse


def test_admin_login_requires_a_valid_role():
    assert AdminLogin(role="company", secret="x").role == "company"
    with pytest.raises(ValidationError):
        AdminLogin(role="root", secret="x")


def test_signup_forbids_extra_fields():
    assert SignupRequest(company_name="Acme").company_name == "Acme"
    with pytest.raises(ValidationError):
        SignupRequest(company_name="Acme", password="sneaky")


def test_enroll_response_has_department_id_field():
    assert "department_id" in EnrollResponse.model_fields
