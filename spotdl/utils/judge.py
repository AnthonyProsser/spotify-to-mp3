"""
Match judge module.

Uses a "System One" decision model (TypeSafe's Jev in the cloud, or Kev
running locally) to decide which search result is the Spotify track.
spotDL's fuzzy matching still ranks the results; the judge picks among the
top candidates and falls back to spotDL's pick when it is not confident.
"""

import csv
import logging
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

from spotdl.types.result import Result
from spotdl.types.song import Song

__all__ = [
    "JUDGE_BACKENDS",
    "JudgeError",
    "JudgeVerdict",
    "MatchJudge",
    "SystemOneClient",
    "create_judge",
]

logger = logging.getLogger(__name__)

MAX_CANDIDATES = 5
NONE_LABEL = "none"

# backend name -> (default base url, default model)
JUDGE_BACKENDS: Dict[str, Tuple[str, str]] = {
    "jev": ("https://api.typesafe.ai", "jev-latest"),
    "kev": ("http://127.0.0.1:8009", "kev-latest"),
    "jev-cloudflare": (
        "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run",
        "typesafe/jev",
    ),
}

REPORT_FIELDS = [
    "song",
    "spotify_url",
    "spotdl_url",
    "spotdl_score",
    "judge_url",
    "judge_choice",
    "judge_confidence",
    "judge_original",
    "final_url",
    "outcome",
]


class JudgeError(Exception):
    """
    Raised when the judge model can't be reached or returns a bad response.
    """


@dataclass(frozen=True)
class JudgeVerdict:
    """
    The judge's answer for one song.
    """

    choice: str  # candidate index as a string, or "none"
    confidence: float  # probability of the chosen label
    original: Optional[float]  # probability the pick is the original studio version


class SystemOneClient:
    """
    Minimal client for the TypeSafe System One API. Kev serves the same API
    locally, and Cloudflare Workers AI wraps it in its own envelope.
    """

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: Optional[str] = None,
        cloudflare: bool = False,
        timeout: float = 15.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.cloudflare = cloudflare
        self.timeout = timeout
        self.session = requests.Session()

    def system_one(self, state: Any, questions: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ask the model questions about a state.

        ### Arguments
        - state: Text or JSON describing what to evaluate.
        - questions: Question definitions keyed by name.

        ### Returns
        - The answers dict, keyed by question name.
        """

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        if self.cloudflare:
            url = self.base_url
            body: Dict[str, Any] = {
                "model": self.model,
                "input": {"state": state, "questions": questions},
            }
        else:
            url = f"{self.base_url}/v1/systemone"
            body = {"state": state, "model": self.model, "questions": questions}

        try:
            response = self.session.post(
                url, json=body, headers=headers, timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError) as exception:
            raise JudgeError(f"Judge request failed: {exception}") from exception

        # Cloudflare wraps model output in {"result": ...}
        if isinstance(data, dict) and isinstance(data.get("result"), dict):
            data = data["result"]

        answers = data.get("answers") if isinstance(data, dict) else None
        if not isinstance(answers, dict):
            raise JudgeError(f"Judge response has no answers: {data!r}")

        return answers


class MatchJudge:
    """
    Picks the correct search result for a song using a System One model.
    """

    def __init__(
        self,
        client: SystemOneClient,
        threshold: float = 0.7,
        judge_all: bool = False,
        report_path: Optional[str] = None,
    ) -> None:
        self.client = client
        self.threshold = threshold
        self.judge_all = judge_all
        self.report_path = Path(report_path) if report_path else None
        self._report_lock = threading.Lock()

    @staticmethod
    def build_state(song: Song, candidates: List[Result]) -> Dict[str, Any]:
        """
        Build a compact state. Kev is trained on states of up to 384 tokens,
        so only the fields that matter for matching are included.
        """

        return {
            "spotify_track": {
                "title": song.name,
                "artists": song.artists,
                "album": song.album_name,
                "duration_s": song.duration,
                "explicit": song.explicit,
            },
            "candidates": {
                str(index): MatchJudge.describe_result(result)
                for index, result in enumerate(candidates)
            },
        }

    @staticmethod
    def describe_result(result: Result) -> Dict[str, Any]:
        """
        Describe a search result for the model, leaving out empty fields.
        """

        description: Dict[str, Any] = {
            "title": result.name,
            "channel": result.author,
            "duration_s": round(result.duration),
            "official_audio": result.verified,
        }

        if result.artists:
            description["artists"] = list(result.artists)
        if result.album:
            description["album"] = result.album
        if result.views:
            description["views"] = result.views

        return description

    @staticmethod
    def build_questions(candidates: List[Result]) -> Dict[str, Any]:
        """
        Build the questions sent to the model.
        """

        criteria: Dict[str, Optional[str]] = {
            str(index): None for index in range(len(candidates))
        }
        criteria[NONE_LABEL] = "None of the candidates is this recording."

        return {
            "best_match": {
                "type": "choice",
                "instructions": (
                    "Which candidate is the same recording as the Spotify track? "
                    "Titles and artist names can be in any language or script, "
                    "translated, transliterated or with different accents, so "
                    "compare meaning, not spelling. Durations should be close. "
                    "Live (en vivo, ao vivo, en directo), cover, remix, "
                    "karaoke, sped up or other versions are wrong unless the "
                    "Spotify track is that version."
                ),
                "criteria": criteria,
            },
            "is_studio_original": {
                "type": "noul",
                "instructions": (
                    "The best matching candidate is the same version as the "
                    "Spotify track, not a live, cover, remix, karaoke, sped up "
                    "or fan-made version."
                ),
            },
        }

    def ask(self, song: Song, candidates: List[Result]) -> JudgeVerdict:
        """
        Ask the model which candidate matches the song.

        ### Arguments
        - song: The Spotify song.
        - candidates: The search results, best spotDL score first.

        ### Returns
        - The model's verdict.
        """

        answers = self.client.system_one(
            self.build_state(song, candidates), self.build_questions(candidates)
        )

        best_match = answers.get("best_match") or {}
        choice = best_match.get("choice")
        probabilities = best_match.get("probabilities") or {}
        if not isinstance(choice, str):
            raise JudgeError(f"Judge returned no choice: {answers!r}")

        confidence = probabilities.get(choice, best_match.get("confidence", 0.0))

        original = (answers.get("is_studio_original") or {}).get("noul")

        return JudgeVerdict(
            choice=choice,
            confidence=float(confidence),
            original=float(original) if original is not None else None,
        )

    @staticmethod
    def build_candidates(
        results: Dict[Result, float],
        spotdl_result: Optional[Result],
        unscored: Optional[List[Result]] = None,
    ) -> List[Result]:
        """
        Build the candidate list: spotDL's scored results first (best score
        first), then results spotDL filtered out. spotDL's filters drop
        results whose titles or artists are spelled differently, which is
        common for songs that aren't in English, so the model gets to see
        them too.
        """

        candidates = [
            result
            for result, _ in sorted(results.items(), key=lambda x: x[1], reverse=True)
        ][:MAX_CANDIDATES]

        # Make sure spotDL's own pick (which also weighs views) is a candidate
        if spotdl_result is not None and spotdl_result not in candidates:
            candidates[-1] = spotdl_result

        for result in unscored or []:
            if len(candidates) >= MAX_CANDIDATES:
                break
            if result not in candidates and result not in results:
                candidates.append(result)

        return candidates

    def choose(
        self,
        song: Song,
        results: Dict[Result, float],
        spotdl_result: Optional[Result],
        spotdl_score: Optional[float],
        unscored: Optional[List[Result]] = None,
    ) -> Optional[Result]:
        """
        Choose the result to download. Falls back to spotDL's pick when the
        judge fails, rejects every candidate, or isn't confident enough.

        ### Arguments
        - song: The Spotify song.
        - results: Search results that passed spotDL's filters, with scores.
        - spotdl_result: The result spotDL would pick on its own, or None if
            spotDL found no match.
        - spotdl_score: spotDL's score for that result.
        - unscored: Search results spotDL filtered out.

        ### Returns
        - The result to download, or None if there is no match.
        """

        candidates = self.build_candidates(results, spotdl_result, unscored)
        if not candidates:
            return spotdl_result

        verdict: Optional[JudgeVerdict] = None
        judge_result: Optional[Result] = None
        final_result = spotdl_result

        try:
            verdict = self.ask(song, candidates)
        except JudgeError as exception:
            logger.warning(
                "Judge failed for %s, using spotDL's pick: %s",
                song.display_name,
                exception,
            )
            outcome = "judge_error"
        else:
            if verdict.choice.isdigit() and int(verdict.choice) < len(candidates):
                judge_result = candidates[int(verdict.choice)]

            if judge_result is None:
                outcome = "rejected_all"
            elif verdict.confidence < self.threshold:
                outcome = "low_confidence"
            elif verdict.original is not None and verdict.original < 0.5:
                outcome = "not_original"
            else:
                final_result = judge_result
                if spotdl_result is None:
                    outcome = "rescued"
                elif judge_result == spotdl_result:
                    outcome = "agreed"
                else:
                    outcome = "overrode"

            logger.debug(
                "[%s] Judge verdict %s (outcome %s)", song.song_id, verdict, outcome
            )

            if outcome not in ("agreed", "overrode", "rescued"):
                logger.info(
                    "Judge is unsure about %s (%s), using spotDL's pick %s",
                    song.display_name,
                    outcome,
                    spotdl_result.url if spotdl_result else None,
                )

        self.write_report(
            {
                "song": song.display_name,
                "spotify_url": song.url,
                "spotdl_url": spotdl_result.url if spotdl_result else "",
                "spotdl_score": (
                    round(spotdl_score, 2) if spotdl_score is not None else ""
                ),
                "judge_url": judge_result.url if judge_result else "",
                "judge_choice": verdict.choice if verdict else "",
                "judge_confidence": round(verdict.confidence, 3) if verdict else "",
                "judge_original": (
                    round(verdict.original, 3)
                    if verdict and verdict.original is not None
                    else ""
                ),
                "final_url": final_result.url if final_result else "",
                "outcome": outcome,
            }
        )

        return final_result

    def write_report(self, row: Dict[str, Any]) -> None:
        """
        Append a row to the judge report CSV, if one is configured.
        """

        if self.report_path is None:
            return

        with self._report_lock:
            new_file = not self.report_path.exists()
            with open(self.report_path, "a", encoding="utf-8", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=REPORT_FIELDS)
                if new_file:
                    writer.writeheader()
                writer.writerow(row)


def create_judge(
    backend: Optional[str],
    url: Optional[str] = None,
    model: Optional[str] = None,
    threshold: float = 0.7,
    judge_all: bool = False,
    report_path: Optional[str] = None,
) -> Optional[MatchJudge]:
    """
    Create a match judge from settings.

    ### Arguments
    - backend: "jev", "jev-cloudflare", "kev", or None to disable the judge.
    - url: Override the backend's base URL.
    - model: Override the backend's model name.
    - threshold: Minimum confidence to accept the judge's pick.
    - judge_all: Judge every song, even when spotDL is already confident.
    - report_path: Where to write the CSV report, or None for no report.

    ### Returns
    - The judge, or None if disabled.
    """

    if not backend:
        return None

    if backend not in JUDGE_BACKENDS:
        raise JudgeError(f"Unknown judge backend: {backend}")

    default_url, default_model = JUDGE_BACKENDS[backend]
    cloudflare = backend == "jev-cloudflare"

    if backend == "jev":
        api_key = os.environ.get("TYPESAFE_API_KEY")
        if not api_key:
            raise JudgeError("Set TYPESAFE_API_KEY to use the jev judge")
    elif cloudflare:
        api_key = os.environ.get("CLOUDFLARE_API_TOKEN")
        account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
        if not api_key or (not account_id and not url):
            raise JudgeError(
                "Set CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID "
                "to use the jev-cloudflare judge"
            )
        default_url = default_url.format(account_id=account_id)
    else:
        # Kev accepts any key
        api_key = os.environ.get("KEV_API_KEY", "local")

    client = SystemOneClient(
        base_url=url or default_url,
        model=model or default_model,
        api_key=api_key,
        cloudflare=cloudflare,
        # A local model can take several seconds when the machine is busy
        # or the model was swapped out
        timeout=60.0 if backend == "kev" else 15.0,
    )

    return MatchJudge(
        client, threshold=threshold, judge_all=judge_all, report_path=report_path
    )
