"""
Unit tests for the deterministic eligibility rule engine.

Why these tests matter:
Eligibility for a government scheme is a real, consequential decision —
a wrong "eligible" or "not_eligible" answer could genuinely mislead a
user about a benefit they qualify for (or don't). Since this project's
core design decision is to keep eligibility logic deterministic and
LLM-free specifically to avoid hallucination risk, these tests are what
let me actually PROVE that decision is correct — not just claim it.

Run with:  pytest tests/test_eligibility.py -v
"""

import pytest
from eligibility import check_eligibility, _to_number, match_all_schemes


# ---------------------------------------------------------------------
# Tests for _to_number() — the type-safety fix for the "3 lakh" bug
# ---------------------------------------------------------------------

class TestToNumber:
    def test_plain_int_passes_through(self):
        assert _to_number(300000) == 300000

    def test_plain_float_passes_through(self):
        assert _to_number(22.5) == 22.5

    def test_none_returns_none(self):
        assert _to_number(None) is None

    def test_numeric_string(self):
        assert _to_number("300000") == 300000.0

    def test_lakh_phrasing(self):
        assert _to_number("3 lakh") == 300000.0

    def test_lakh_phrasing_no_space(self):
        assert _to_number("3lakh") == 300000.0

    def test_lac_phrasing(self):
        assert _to_number("3 lac") == 300000.0

    def test_crore_phrasing(self):
        assert _to_number("1 crore") == 10000000.0

    def test_comma_formatted_string(self):
        assert _to_number("3,00,000") == 300000.0

    def test_string_with_rupee_symbol(self):
        assert _to_number("₹300000") == 300000.0

    def test_string_with_years_suffix(self):
        assert _to_number("22 years") == 22.0

    def test_garbage_string_returns_none(self):
        assert _to_number("not a number") is None

    def test_empty_string_returns_none(self):
        assert _to_number("") is None


# ---------------------------------------------------------------------
# Fixtures — sample scheme definitions used across multiple tests
# ---------------------------------------------------------------------

@pytest.fixture
def farmer_scheme():
    return {
        "id": "test_farmer_scheme",
        "name": "Test Farmer Support Scheme",
        "eligibility": {
            "occupation": ["farmer"],
            "income_max": 250000,
            "age_min": 18,
            "age_max": 60,
            "gender": "any",
            "location": "any",
        },
    }


@pytest.fixture
def women_only_scheme():
    return {
        "id": "test_women_scheme",
        "name": "Test Women Welfare Scheme",
        "eligibility": {
            "occupation": "any",
            "gender": "female",
            "age_min": 18,
            "age_max": 45,
        },
    }


@pytest.fixture
def senior_citizen_scheme():
    return {
        "id": "test_senior_scheme",
        "name": "Test Senior Citizen Pension",
        "eligibility": {
            "age_min": 60,
        },
    }


@pytest.fixture
def excluded_flag_scheme():
    return {
        "id": "test_excl_scheme",
        "name": "Test Scheme With Exclusion",
        "eligibility": {
            "occupation": "any",
            "exclusions": ["income_tax_payer"],
        },
    }


# ---------------------------------------------------------------------
# Eligible cases
# ---------------------------------------------------------------------

class TestEligibleCases:
    def test_fully_matching_profile_is_eligible(self, farmer_scheme):
        profile = {
            "occupation": "farmer",
            "annual_income": 100000,
            "age": 30,
            "gender": "male",
            "location": "delhi",
        }
        result = check_eligibility(farmer_scheme, profile)
        assert result["status"] == "eligible"
        assert result["missing_fields"] == []

    def test_eligible_with_string_income_and_age(self, farmer_scheme):
        # Regression test for the real bug found while testing locally:
        # LLM sometimes extracts income/age as strings like "3 lakh"
        # rather than plain numbers, which used to crash with:
        # TypeError: '<=' not supported between instances of 'str' and 'int'
        profile = {
            "occupation": "farmer",
            "annual_income": "1 lakh",
            "age": "30 years",
            "gender": "male",
            "location": "delhi",
        }
        result = check_eligibility(farmer_scheme, profile)
        assert result["status"] == "eligible"

    def test_women_scheme_eligible_for_matching_profile(self, women_only_scheme):
        profile = {"gender": "female", "age": 25, "occupation": "student"}
        result = check_eligibility(women_only_scheme, profile)
        assert result["status"] == "eligible"


# ---------------------------------------------------------------------
# Not-eligible cases — one per field, to make sure each check
# independently disqualifies correctly
# ---------------------------------------------------------------------

class TestNotEligibleCases:
    def test_income_too_high_is_not_eligible(self, farmer_scheme):
        profile = {
            "occupation": "farmer",
            "annual_income": 900000,
            "age": 30,
            "gender": "male",
            "location": "delhi",
        }
        result = check_eligibility(farmer_scheme, profile)
        assert result["status"] == "not_eligible"

    def test_wrong_occupation_is_not_eligible(self, farmer_scheme):
        profile = {
            "occupation": "government employee",
            "annual_income": 100000,
            "age": 30,
            "gender": "male",
            "location": "delhi",
        }
        result = check_eligibility(farmer_scheme, profile)
        assert result["status"] == "not_eligible"

    def test_age_below_minimum_is_not_eligible(self, farmer_scheme):
        profile = {
            "occupation": "farmer",
            "annual_income": 100000,
            "age": 15,
            "gender": "male",
            "location": "delhi",
        }
        result = check_eligibility(farmer_scheme, profile)
        assert result["status"] == "not_eligible"

    def test_age_above_maximum_is_not_eligible(self, farmer_scheme):
        profile = {
            "occupation": "farmer",
            "annual_income": 100000,
            "age": 70,
            "gender": "male",
            "location": "delhi",
        }
        result = check_eligibility(farmer_scheme, profile)
        assert result["status"] == "not_eligible"

    def test_wrong_gender_is_not_eligible(self, women_only_scheme):
        profile = {"gender": "male", "age": 25}
        result = check_eligibility(women_only_scheme, profile)
        assert result["status"] == "not_eligible"

    def test_excluded_flag_disqualifies_even_if_other_fields_match(self, excluded_flag_scheme):
        profile = {"occupation": "farmer", "flags": ["income_tax_payer"]}
        result = check_eligibility(excluded_flag_scheme, profile)
        assert result["status"] == "not_eligible"


# ---------------------------------------------------------------------
# Possibly-eligible cases — the tri-state ("unknown") logic
# ---------------------------------------------------------------------

class TestPossiblyEligibleCases:
    def test_missing_age_gives_possibly_eligible(self, senior_citizen_scheme):
        profile = {"occupation": "any"}  # age not provided at all
        result = check_eligibility(senior_citizen_scheme, profile)
        assert result["status"] == "possibly_eligible"
        assert "age" in result["missing_fields"]

    def test_missing_occupation_gives_possibly_eligible(self, farmer_scheme):
        profile = {
            "annual_income": 100000,
            "age": 30,
            "gender": "male",
            "location": "delhi",
            # occupation intentionally omitted
        }
        result = check_eligibility(farmer_scheme, profile)
        assert result["status"] == "possibly_eligible"
        assert "occupation" in result["missing_fields"]

    def test_missing_income_gives_possibly_eligible(self, farmer_scheme):
        profile = {
            "occupation": "farmer",
            "age": 30,
            "gender": "male",
            "location": "delhi",
            # annual_income intentionally omitted
        }
        result = check_eligibility(farmer_scheme, profile)
        assert result["status"] == "possibly_eligible"
        assert "annual_income" in result["missing_fields"]

    def test_unparseable_income_is_treated_as_missing_not_crash(self, farmer_scheme):
        # A garbage/unparseable income string should NOT crash the check —
        # it should be treated the same as "unknown".
        profile = {
            "occupation": "farmer",
            "annual_income": "not a real number",
            "age": 30,
            "gender": "male",
            "location": "delhi",
        }
        result = check_eligibility(farmer_scheme, profile)
        assert result["status"] == "possibly_eligible"
        assert "annual_income" in result["missing_fields"]


# ---------------------------------------------------------------------
# Boundary / edge cases
# ---------------------------------------------------------------------

class TestBoundaryCases:
    def test_income_exactly_at_max_is_eligible(self, farmer_scheme):
        profile = {
            "occupation": "farmer",
            "annual_income": 250000,  # exactly equal to income_max
            "age": 30,
            "gender": "male",
            "location": "delhi",
        }
        result = check_eligibility(farmer_scheme, profile)
        assert result["status"] == "eligible"

    def test_age_exactly_at_minimum_is_eligible(self, farmer_scheme):
        profile = {
            "occupation": "farmer",
            "annual_income": 100000,
            "age": 18,  # exactly equal to age_min
            "gender": "male",
            "location": "delhi",
        }
        result = check_eligibility(farmer_scheme, profile)
        assert result["status"] == "eligible"

    def test_age_exactly_at_maximum_is_eligible(self, farmer_scheme):
        profile = {
            "occupation": "farmer",
            "annual_income": 100000,
            "age": 60,  # exactly equal to age_max
            "gender": "male",
            "location": "delhi",
        }
        result = check_eligibility(farmer_scheme, profile)
        assert result["status"] == "eligible"


# ---------------------------------------------------------------------
# match_all_schemes() — the higher-level function used by app.py/agent.py
# ---------------------------------------------------------------------

class TestMatchAllSchemes:
    def test_returns_dict_with_expected_keys(self):
        profile = {"occupation": "farmer", "age": 30}
        result = match_all_schemes(profile)
        assert "eligible" in result
        assert "possibly_eligible" in result
        assert isinstance(result["eligible"], list)
        assert isinstance(result["possibly_eligible"], list)

    def test_empty_profile_does_not_crash(self):
        # A completely empty profile should never crash the engine —
        # every scheme should just fall into eligible/possibly_eligible
        # gracefully based on what's unknown.
        result = match_all_schemes({})
        assert isinstance(result, dict)