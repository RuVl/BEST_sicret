from collections.abc import Callable
from functools import partial

from fuzzywuzzy import process


class FuzzyItem[T]:
    def __init__(self, obj: T, extractor: Callable[[T], str]):
        self.obj = obj
        self.extractor = extractor
        self.name = None

    def __str__(self):
        if self.name is None:
            self.name = self.extractor(self.obj)
        return self.name


def fuzzy_search_bests[T](
    query: str,
    data: list[T],
    threshold: int = 70,
    limit: int | None = None,
    extractor: Callable[[T], str] = str,
) -> list[T]:
    choices = map(partial(FuzzyItem, extractor=extractor), data)
    search_results = process.extractBests(query, choices, score_cutoff=threshold, limit=limit)
    return [fuzzy_item.obj for fuzzy_item, score in search_results]
