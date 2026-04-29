from fuzzywuzzy import process


def fuzzy_search(query: str, names: list[str], threshold: int = 50) -> list[str]:
    results = process.extract(query, names, limit=None)
    return [name for name, score in results if score >= threshold]