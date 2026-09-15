"""Validation rules for the frozen AutoZone benchmark."""

from typing import Any, Dict


REQUIRED_FIELDS = ["product_name", "part_number", "price", "availability"]


def _present(value: Any) -> bool:
    return value is not None and value != "" and value != [] and value != {}


def validate(data: Dict[str, Any], expected_store: Dict[str, Any]) -> Dict[str, Any]:
    missing = [field for field in REQUIRED_FIELDS if not _present(data.get(field))]

    observed_store = str(data.get("store_id")) if data.get("store_id") is not None else None
    expected_store_id = str(expected_store.get("store_id"))
    store_match = observed_store == expected_store_id if observed_store else None

    # Location/store verification is deliberately explicit. A provider that
    # returns product data without evidence of the requested store is not
    # treated as a fully validated ZIP-localized success.
    zip_verified = bool(
        data.get("zip") == expected_store.get("zip")
        or data.get("location_zip") == expected_store.get("zip")
        or store_match is True
    )

    validated_success = not missing and zip_verified

    return {
        "validated_success": validated_success,
        "missing_required_fields": missing,
        "zip_verified": zip_verified,
        "store_detected": observed_store,
        "store_match": store_match,
    }
