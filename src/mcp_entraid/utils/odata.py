from urllib.parse import quote


def encode_path_segment(value: str) -> str:
    return quote(value, safe="")


def select_params(fields: list[str]) -> dict[str, str]:
    return {"$select": ",".join(fields)}
