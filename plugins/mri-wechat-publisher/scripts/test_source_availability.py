#!/usr/bin/env python3
"""Offline tests for metadata-only source availability checks."""

from __future__ import annotations

import copy
import unittest
import urllib.error
from datetime import date

import source_availability as access
from search_literature_candidates import score_record


class SourceAvailabilityTest(unittest.TestCase):
    def test_pmcid_confirms_public_fulltext_and_supplement(self) -> None:
        def fake_fetch(url: str, timeout: int) -> dict:
            self.assertIn("europepmc", url)
            return {
                "resultList": {
                    "result": [
                        {
                            "id": "12345",
                            "pmcid": "PMC12345",
                            "isOpenAccess": "Y",
                            "inPMC": "Y",
                            "hasSuppl": "Y",
                        }
                    ]
                }
            }

        result = access.probe_candidate(
            {"pmid": "12345", "pmcid": "PMC12345"},
            fetch_json=fake_fetch,
            checked_at="2026-08-10T17:00:00+08:00",
        )
        self.assertEqual(result["status"], "PUBLIC_FULLTEXT_CONFIRMED")
        self.assertEqual(result["supplement"]["status"], "PUBLIC_AVAILABLE")
        self.assertFalse(result["downloaded_content"])

    def test_closed_metadata_requires_user_upload(self) -> None:
        def fake_fetch(url: str, timeout: int) -> dict:
            if "europepmc" in url:
                return {
                    "resultList": {
                        "result": [
                            {
                                "id": "999",
                                "isOpenAccess": "N",
                                "hasSuppl": "Y",
                            }
                        ]
                    }
                }
            return {
                "results": [
                    {
                        "id": "https://openalex.org/W1",
                        "open_access": {"is_oa": False, "oa_status": "closed"},
                        "best_oa_location": None,
                    }
                ]
            }

        result = access.probe_candidate(
            {"pmid": "999", "doi": "10.1000/closed"},
            fetch_json=fake_fetch,
            checked_at="2026-08-10T17:00:00+08:00",
        )
        self.assertEqual(result["status"], "USER_UPLOAD_REQUIRED")
        self.assertEqual(result["supplement"]["status"], "DETECTED_RESTRICTED")
        self.assertFalse(result["downloaded_content"])

    def test_api_failures_remain_unknown(self) -> None:
        def fail_fetch(url: str, timeout: int) -> dict:
            raise urllib.error.URLError("offline")

        result = access.probe_candidate(
            {"pmid": "888", "doi": "10.1000/unknown"},
            fetch_json=fail_fetch,
            checked_at="2026-08-10T17:00:00+08:00",
        )
        self.assertEqual(result["status"], "ACCESS_UNKNOWN")
        self.assertGreaterEqual(len(result["errors"]), 2)

    def test_enrichment_does_not_change_scientific_score(self) -> None:
        payload = {
            "candidates": [
                {
                    "choice": 1,
                    "title": "MRI paper",
                    "score": 97,
                    "pmcid": "PMC1",
                }
            ]
        }

        def fake_fetch(url: str, timeout: int) -> dict:
            return {"resultList": {"result": []}}

        enriched = access.enrich_payload(payload, fetch_json=fake_fetch)
        self.assertEqual(enriched["candidates"][0]["score"], 97)
        self.assertEqual(
            enriched["candidates"][0]["fulltext_access"]["status"],
            "PUBLIC_FULLTEXT_CONFIRMED",
        )
        self.assertTrue(
            enriched["fulltext_check_policy"]["scientific_score_independent"]
        )

    def test_open_access_signals_do_not_change_scientific_rank(self) -> None:
        base = {
            "title": "Functional MRI network prediction",
            "abstract": "Functional magnetic resonance imaging cognition network prediction",
            "doi": "10.1000/example",
            "pmid": "123",
            "journal": "Nature Neuroscience",
            "publication_date": "2026-07-01",
        }
        closed = score_record(copy.deepcopy(base), date(2026, 8, 10))
        public = copy.deepcopy(base)
        public.update(
            {
                "pmcid": "PMC123",
                "open_access": {"is_oa": True, "oa_status": "gold"},
                "best_oa_location": {"pdf_url": "https://example.org/paper.pdf"},
            }
        )
        public = score_record(public, date(2026, 8, 10))
        self.assertEqual(closed["total_score"], public["total_score"])
        self.assertEqual(closed["score_components"], public["score_components"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
