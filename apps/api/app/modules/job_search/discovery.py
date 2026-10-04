"""Fair candidate intake across queries, retaining posting identity and a hard fetch bound."""

from itertools import zip_longest

from app.modules.job_search.posting import _is_listing_page, _source_for_url, canonicalize_job_url
from app.modules.job_search.providers import SearchResponse
from app.modules.job_search.records import _Candidate


def collect_candidates(responses: list[SearchResponse]) -> list[_Candidate]:
    candidates: list[_Candidate] = []
    seen: set[str] = set()
    for row in zip_longest(*(response.hits for response in responses)):
        for hit in row:
            if hit is None:
                continue
            canonical = canonicalize_job_url(hit.url)
            if not canonical or canonical in seen or _is_listing_page(hit.url, hit.title):
                continue
            seen.add(canonical)
            candidates.append(
                _Candidate(
                    len(candidates),
                    hit.title[:240],
                    hit.url[:2000],
                    canonical[:2000],
                    hit.snippet[:800],
                    _source_for_url(hit.url),
                )
            )
            if len(candidates) == 30:
                return candidates
    return candidates
