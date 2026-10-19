"""Tiny, deterministic data validation acceptance fixture."""

def valid_record(record: dict) -> bool:
    return (isinstance(record, dict)
            and type(record.get("id")) is int and record["id"] > 0
            and isinstance(record.get("name"), str) and bool(record["name"].strip()))
