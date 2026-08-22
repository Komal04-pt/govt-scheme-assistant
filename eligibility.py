import json
import os
import re
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.environ.get("MONGODB_URI")
DB_NAME = "janseva_db"
COLLECTION_NAME = "schemes"

try:
    _client = MongoClient(MONGODB_URI)
    _db = _client[DB_NAME]
    SCHEMES = list(_db[COLLECTION_NAME].find({}, {"_id": 0}))
    if not SCHEMES:
        print("Warning: No schemes found in MongoDB — check migration ran successfully.")
except Exception as e:
    SCHEMES = []
    print(f"Warning: Failed to load schemes from MongoDB: {e}")


def _to_number(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return value

    if isinstance(value, str):
        s = value.lower().strip()
        s = s.replace(",", "")

        if not s:
            return None

        lakh_match = re.match(r"^([\d.]+)\s*(lakh|lac)s?$", s)
        if lakh_match:
            return float(lakh_match.group(1)) * 100000

        crore_match = re.match(r"^([\d.]+)\s*crores?$", s)
        if crore_match:
            return float(crore_match.group(1)) * 10000000

        cleaned = re.sub(r"[^\d.]", "", s)
        if cleaned:
            try:
                return float(cleaned)
            except ValueError:
                return None

    return None


def _matches_occupation(scheme_occ, user_occ):
    if not scheme_occ:
        return True

    if isinstance(scheme_occ, str):
        scheme_occ = [scheme_occ.lower()]
    else:
        scheme_occ = [str(o).lower() for o in scheme_occ]

    if "any" in scheme_occ or "all" in scheme_occ:
        return True

    if user_occ is None:
        return None

    return str(user_occ).lower().strip() in scheme_occ


def _matches_income(income_max, user_income):
    if income_max is None:
        return True
    user_income = _to_number(user_income)
    if user_income is None:
        return None
    return user_income <= income_max


def _matches_age(age_min, age_max, user_age):
    if age_min is None and age_max is None:
        return True
    user_age = _to_number(user_age)
    if user_age is None:
        return None
    if age_min is not None and user_age < age_min:
        return False
    if age_max is not None and user_age > age_max:
        return False
    return True


def _matches_gender(scheme_gender, user_gender):
    if not scheme_gender:
        return True

    scheme_gender = str(scheme_gender).lower().strip()
    if scheme_gender in ["any", "all"]:
        return True

    if user_gender is None:
        return None

    user_gender = str(user_gender).lower().strip()
    return scheme_gender == user_gender


def _matches_location(scheme_location, user_location):
    if not scheme_location:
        return True

    scheme_location = str(scheme_location).lower().strip()
    if scheme_location in ["any", "all", "central"]:
        return True

    if user_location is None:
        return None

    user_location = str(user_location).lower().strip()
    return scheme_location == user_location


def _matches_exclusions(exclusions, user_flags):
    if not exclusions or not user_flags:
        return True

    user_flags_norm = [str(f).lower().strip() for f in user_flags]
    for ex in exclusions:
        if str(ex).lower().strip() in user_flags_norm:
            return False
    return True


def check_eligibility(scheme, profile):
    profile = dict(profile)
    profile["annual_income"] = _to_number(profile.get("annual_income"))
    profile["age"] = _to_number(profile.get("age"))

    elig = scheme.get("eligibility", {})
    checks = []
    missing = []

    occ_result = _matches_occupation(elig.get("occupation"), profile.get("occupation"))
    if occ_result is None:
        missing.append("occupation")
    else:
        checks.append(occ_result)

    income_result = _matches_income(elig.get("income_max"), profile.get("annual_income"))
    if income_result is None and elig.get("income_max") is not None:
        missing.append("annual_income")
    elif income_result is not None:
        checks.append(income_result)

    age_result = _matches_age(elig.get("age_min"), elig.get("age_max"), profile.get("age"))
    if age_result is None and (elig.get("age_min") is not None or elig.get("age_max") is not None):
        missing.append("age")
    elif age_result is not None:
        checks.append(age_result)

    gender_result = _matches_gender(elig.get("gender"), profile.get("gender"))
    if gender_result is None and elig.get("gender"):
        missing.append("gender")
    elif gender_result is not None:
        checks.append(gender_result)

    location_result = _matches_location(elig.get("location"), profile.get("location"))
    if location_result is None and elig.get("location"):
        missing.append("location")
    elif location_result is not None:
        checks.append(location_result)

    if elig.get("land_owner") is not None:
        if profile.get("land_owner") is None:
            missing.append("land_owner")
        else:
            checks.append(profile.get("land_owner") == elig.get("land_owner"))

    excl_result = _matches_exclusions(elig.get("exclusions"), profile.get("flags", []))
    checks.append(excl_result)

    if not all(checks):
        return {"status": "not_eligible", "missing_fields": [], "scheme_id": scheme.get("id")}

    if missing:
        return {"status": "possibly_eligible", "missing_fields": missing, "scheme_id": scheme.get("id")}

    return {"status": "eligible", "missing_fields": [], "scheme_id": scheme.get("id")}


def match_all_schemes(profile):
    eligible = []
    possibly_eligible = []

    for scheme in SCHEMES:
        result = check_eligibility(scheme, profile)
        if result["status"] == "eligible":
            eligible.append(scheme)
        elif result["status"] == "possibly_eligible":
            possibly_eligible.append((scheme, result["missing_fields"]))

    return {"eligible": eligible, "possibly_eligible": possibly_eligible}


def get_scheme_by_id(scheme_id):
    for s in SCHEMES:
        if s.get("id") == scheme_id:
            return s
    return None

def search_scheme_by_name(query_name):
    if not query_name:
        return None
    query_lower = query_name.lower().strip()
    for s in SCHEMES:
        scheme_name = str(s.get("name", "")).lower()
        scheme_name_hi = str(s.get("name_hi", "")).lower()
        if query_lower in scheme_name or scheme_name in query_lower:
            return s
        if scheme_name_hi and (query_lower in scheme_name_hi or scheme_name_hi in query_lower):
            return s
    return None