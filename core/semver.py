import re
from typing import Tuple

_VERSION_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)")


def parse_version(version_string: str) -> Tuple[int, int, int]:
    match = _VERSION_RE.match(version_string.strip())
    if not match:
        return (0, 0, 0)
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)))


def compare_versions(version_a: str, version_b: str) -> int:
    parsed_a = parse_version(version_a)
    parsed_b = parse_version(version_b)
    if parsed_a < parsed_b:
        return -1
    if parsed_a > parsed_b:
        return 1
    return 0


def is_newer(candidate_version: str, current_version: str) -> bool:
    return compare_versions(candidate_version, current_version) > 0
