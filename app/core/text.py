import re
import unicodedata

#
#   Normalizes text strings by removing white spaces on start and end and
#   replacing special characters with their normal counterparts
#
def normalize_text(value: str | None) -> str:
    if value is None:
        return ""

    #   Trim leading and trailing whitespace
    value = str(value).strip()
    #   Collapse repeated internal spaces
    value = re.sub(r"\s+", " ", value)
    #   Decompose accented characters (ã -> a~)
    value = unicodedata.normalize("NFKD", value)
    #   Joins only the simple characters
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    #   Returns the final result in lowercase
    return value.lower()