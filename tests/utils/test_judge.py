import csv

import pytest

from spotdl.providers.audio import base as audio_base
from spotdl.providers.audio.base import AudioProvider
from spotdl.types.result import Result
from spotdl.types.song import Song
from spotdl.utils.judge import JudgeError, MatchJudge, SystemOneClient, create_judge

SONG = Song(
    name="Midnight City",
    artists=["M83"],
    artist="M83",
    genres=[],
    disc_number=1,
    disc_count=1,
    album_name="Hurry Up, We're Dreaming",
    album_artist="M83",
    duration=244,
    year=2011,
    date="2011-10-18",
    track_number=2,
    tracks_count=22,
    song_id="1eyzqe2QqGZUmfcPZtrIyt",
    explicit=False,
    publisher="Mute",
    url="https://open.spotify.com/track/1eyzqe2QqGZUmfcPZtrIyt",
    isrc=None,
    cover_url=None,
    copyright_text=None,
)


def make_result(result_id: str, name: str, duration: float, verified: bool = True):
    return Result(
        source="YouTubeMusic",
        url=f"https://music.youtube.com/watch?v={result_id}",
        verified=verified,
        name=name,
        duration=duration,
        author="M83",
        result_id=result_id,
        views=1000,
    )


LIVE = make_result("live", "Midnight City (Live)", 300)
STUDIO = make_result("studio", "Midnight City", 244)
COVER = make_result("cover", "Midnight City (Cover)", 240, verified=False)

# spotDL scores, LIVE ranked first on purpose
RESULTS = {LIVE: 90.0, STUDIO: 85.0, COVER: 60.0}


class FakeClient:
    def __init__(self, answers=None, error=None):
        self.answers = answers
        self.error = error
        self.calls = []

    def system_one(self, state, questions):
        self.calls.append((state, questions))
        if self.error:
            raise self.error
        return self.answers


def answers(choice, probability, original=0.9):
    return {
        "best_match": {
            "type": "choice",
            "choice": choice,
            "confidence": probability,
            "probabilities": {choice: probability},
        },
        "is_studio_original": {"type": "noul", "noul": original},
    }


@pytest.mark.parametrize(
    "fake_answers, error, expected, outcome",
    [
        (answers("1", 0.95), None, STUDIO, "overrode"),
        (answers("0", 0.95), None, LIVE, "agreed"),
        (answers("1", 0.5), None, LIVE, "low_confidence"),
        (answers("none", 0.95), None, LIVE, "rejected_all"),
        (answers("1", 0.95, original=0.1), None, LIVE, "not_original"),
        (None, JudgeError("boom"), LIVE, "judge_error"),
    ],
)
def test_choose(tmp_path, fake_answers, error, expected, outcome):
    report = tmp_path / "report.csv"
    judge = MatchJudge(
        FakeClient(fake_answers, error), threshold=0.7, report_path=str(report)
    )

    assert judge.choose(SONG, RESULTS, LIVE, 90.0) == expected

    with open(report, encoding="utf-8") as file:
        rows = list(csv.DictReader(file))

    assert len(rows) == 1
    assert rows[0]["outcome"] == outcome
    assert rows[0]["final_url"] == expected.url


def test_candidates_in_score_order():
    client = FakeClient(answers("0", 0.9))
    MatchJudge(client).choose(SONG, RESULTS, LIVE, 90.0)

    state, questions = client.calls[0]
    assert [c["title"] for c in state["candidates"].values()] == [
        LIVE.name,
        STUDIO.name,
        COVER.name,
    ]
    assert state["spotify_track"]["duration_s"] == 244
    assert set(questions["best_match"]["criteria"]) == {"0", "1", "2", "none"}


def test_spotdl_pick_always_a_candidate():
    results = {make_result(str(i), f"Song {i}", 244): 90.0 - i for i in range(8)}
    spotdl_pick = make_result("7", "Song 7", 244)
    client = FakeClient(answers("0", 0.9))

    MatchJudge(client).choose(SONG, results, spotdl_pick, 83.0)

    state, _ = client.calls[0]
    assert len(state["candidates"]) == 5
    assert state["candidates"]["4"]["title"] == "Song 7"


def test_client_request_format(monkeypatch):
    sent = {}

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"model": "kev-latest", "answers": answers("0", 0.9)}

    def fake_post(url, json, headers, timeout):
        sent.update(url=url, json=json, headers=headers)
        return FakeResponse()

    client = SystemOneClient("http://127.0.0.1:8009/", "kev-latest", api_key="local")
    monkeypatch.setattr(client.session, "post", fake_post)

    assert client.system_one({"a": 1}, {"q": {"type": "noul"}})["best_match"]
    assert sent["url"] == "http://127.0.0.1:8009/v1/systemone"
    assert sent["json"] == {
        "state": {"a": 1},
        "model": "kev-latest",
        "questions": {"q": {"type": "noul"}},
    }
    assert sent["headers"]["Authorization"] == "Bearer local"


def test_cloudflare_client_unwraps_result(monkeypatch):
    sent = {}

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"success": True, "result": {"answers": answers("0", 0.9)}}

    def fake_post(url, json, headers, timeout):
        sent.update(url=url, json=json)
        return FakeResponse()

    client = SystemOneClient(
        "https://cf.example/ai/run", "typesafe/jev", api_key="t", cloudflare=True
    )
    monkeypatch.setattr(client.session, "post", fake_post)

    assert client.system_one("s", {})["best_match"]["choice"] == "0"
    assert sent["url"] == "https://cf.example/ai/run"
    assert sent["json"] == {
        "model": "typesafe/jev",
        "input": {"state": "s", "questions": {}},
    }


def test_create_judge(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)

    assert create_judge(None) is None

    with pytest.raises(JudgeError):
        create_judge("jev")

    with pytest.raises(JudgeError):
        create_judge("unknown")

    judge = create_judge("kev", threshold=0.8, judge_all=True)
    assert judge is not None
    assert judge.client.base_url == "http://127.0.0.1:8009"
    assert judge.client.model == "kev-latest"
    assert judge.threshold == 0.8
    assert judge.judge_all


class FakeProvider(AudioProvider):
    SUPPORTS_ISRC = False
    GET_RESULTS_OPTS = [{}]

    def get_results(self, search_term, **kwargs):
        return list(RESULTS)


@pytest.fixture
def provider(monkeypatch):
    monkeypatch.setattr(
        audio_base, "order_results", lambda results, song, query: dict(RESULTS)
    )
    return FakeProvider()


def test_search_without_judge_unchanged(provider):
    spotdl_pick, _ = provider.get_best_result(dict(RESULTS))
    assert provider.search(SONG) == spotdl_pick.url


def test_search_with_judge_all(provider):
    client = FakeClient(answers("0", 0.95))
    provider.judge = MatchJudge(client, judge_all=True)

    assert provider.search(SONG) == LIVE.url
    assert len(client.calls) == 1


def test_search_confident_match_skips_judge(provider):
    spotdl_pick, _ = provider.get_best_result(dict(RESULTS))
    client = FakeClient(answers("0", 0.95))
    provider.judge = MatchJudge(client)

    assert provider.search(SONG) == spotdl_pick.url
    assert not client.calls
