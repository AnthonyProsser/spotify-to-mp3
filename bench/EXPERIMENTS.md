# Experiments

Each entry: the change, then correct / wrong / unsure / unmatched per
playlist, then the judge's overrides and latency. Errors = wrong + unsure +
unmatched; unsure counts as an error until it has been listened to
(`bench/listen.md`).

Playlists: Spanish `5VskdvX3OlGVAHhn1jgoAm` (51), English
`4PniezFG51rrLjQhkWqHsC` (174), Friend's picks `0ADNLtVRNIEIvLNNqxykGG` (144,
held out: baseline and finished candidates only).

## 0. Baseline (2026-09-22)

- Code: `claude/keen-newton-54hz90` at `e2ebaee5`, no matching changes. Judge
  off (`scripts/judge_benchmark.py` without `--judge`).
- Runs: `bench/baseline_{es,en,friend}.csv`, pick details in
  `bench/baseline_*_picks.jsonl`, labels in
  `bench/labels/labels_baseline_*.tsv`.
- Searches, yt-dlp metadata and Spotify data are cached in `bench/cache/`
  (755 files, 5 MB). Rerunning with `--cache bench/cache` reads only the
  cache: the Spanish rerun gave identical picks in about 2 s.

| Playlist | Songs | Correct | Wrong | Unsure | Unmatched | Errors | Error rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| Spanish | 51 | 46 | 2 | 3 | 0 | 5 | 9.8% |
| English | 174 | 158 | 1 | 15 | 0 | 16 | 9.2% |
| Friend's picks (held out) | 144 | 140 | 2 | 2 | 0 | 4 | 2.8% |
| Tuning set (Spanish + English) | 225 | 204 | 3 | 18 | 0 | 21 | 9.3% |
| All | 369 | 344 | 5 | 20 | 0 | 25 | 6.8% |

If every unsure pick turns out correct, the error rates are 3.9% (Spanish),
0.6% (English) and 1.4% (held out).

- Judge overrides: none (judge off). Judge latency: n/a. Search time per song
  (mostly cached view counts): mean 2.0 s Spanish, 2.0 s English, 1.7 s held
  out.
- Wrong: La Bicicleta (music video, +9 s; in both Spanish and held out),
  Bailar (official video, +11 s), Whole Lotta Love (live at the Royal Albert
  Hall), Closer (live at the 2016 VMAs).
- Unsure, by kind:
  - Music videos or fan uploads 5-9 s off: Don't Stop Me Now, Paranoid,
    Play The Game, Fat Bottomed Girls, Under Pressure (x2), Ramble On,
    Footloose, Upside Down, Criminal.
  - Official audio 12 s longer than Spotify: Rock and Roll Ain't Noise
    Pollution, Free Bird.
  - A different remaster year than Spotify's: Hot for Teacher (2004 vs
    2015), Space Truckin' (2024 vs 2012), Killer Queen and Radio Ga Ga (fan
    uploads labelled 2021 vs 2011).
  - Other version or artist: Acróstico (Milan + Sasha?), Ella Baila Sola (a
    "Vizcente Fernández, PesPluma" sound-alike release), Nice To Meet You
    (feat. Lainey Wilson version), Smooth Criminal (lyrics upload).
- Changes from the first round's notes in `GOAL.md`: all 51 Spanish picks
  are the same as `fix1`. Ella Baila Sola is now unsure: `fix1` counted it
  correct by default, but the pick is a knockoff release. Great Balls of
  Fire is now correct: spotDL now picks the official 111 s "Original" instead
  of the earlier 101 s upload.
- Labelling rules: same song, artist and version. Fan, lyrics and official
  uploads within about 5 s with no version words count as correct. A
  different remaster year is unsure. Live, edit or remix versions the Spotify
  track isn't are wrong.

### Kev-4B on this machine (for the judge experiments)

- RTX 4060 8 GB, i5-12600KF, 16 GB RAM, Windows 11. Kev-4B in bf16 needs
  about 9.3 GB of weights, so it doesn't fit the GPU. On the CPU, fp32 (18.7
  GB) doesn't fit in RAM.
- Served with the base model quantized to 8-bit (bitsandbytes). This is a
  local patch to Kev (`KEV_QUANT=8bit`, not in upstream; LoRA unmerged,
  CUDA torch 2.8.0+cu128, no flash-linear-attention):
  `KEV_QUANT=8bit KEV_DTYPE=bf16 uv run --no-sync python -m kev.serve --run jaredpalmer/kev-4b --port 8009`
- Latency on 30 logged judge states (`fix1_en_t07_requests.jsonl`, choice
  + noul): median 675 ms, mean 688 ms, p95 735 ms. README ticket (3
  questions): median 692 ms.
- Peak memory: GPU 6.1 GB in use on the whole card (about 5.5 GB for Kev).
  Server process RAM peak 3.7 GB.
- 8-bit weights can shift probabilities slightly from the published fp32
  numbers. Check before trusting thresholds tuned elsewhere.

## 1. Matching fixes: artists, remaster notes, album editions, versions, length (2026-09-22)

Code changes (`spotdl/utils/matching.py`, `spotdl/utils/versions.py`,
`spotdl/providers/audio/base.py`), each with unit tests:

1. Main artist: compare Spotify's main artist with every result artist.
   Before, it was compared only with the result artist that sorted first,
   so "Eslabon Armado" was checked against "Peso Pluma". When the result
   has one artist and the song several, the main artist alone can match.
   YouTube Music lists "Under Pressure (feat. David Bowie)" by Queen only,
   which used to score 0.
2. Featured artists named in the result's title count as matched.
3. Name match ignores Spotify's remaster note ("Killer Queen - Remastered
   2011" vs "Killer Queen"; the official audio used to fail the 60% name
   cutoff) and artist-only credits in the result's brackets ("Ella Baila
   Sola (Peso Pluma)", "Bailar (mit Pitbull & Elvis Crespo)").
4. New version check: words in a result's brackets that aren't in the song
   name, the artists or a neutral list (official, video, lyrics, ...) cost
   20 points. It catches "(This Time for Africa)", "(Rah Mix)" and "(2004
   Remaster)" vs a 2015 remaster. Stems ("isolated", "drumless", "backing
   track", "multitrack") are now forbidden words.
5. Album match ignores edition notes ("Jazz" = "Jazz (Deluxe Edition)"),
   and the album penalty applies only when the length also differs by more
   than 2 s. Spotify lists compilations, singles and remasters where
   YouTube Music lists the original album. That used to push official audio
   below music videos, which have no album.
6. A close match (score > 85) now keeps its length in the score: 3 points
   per second beyond 2 s. Before, a music video with an intro tied the audio
   at 100 and won on views.
7. `get_best_result` compares scores plus the view bonus before capping at
   100. The cap used to make ties that list order decided.

The Waka Waka regression from the first album-penalty attempt doesn't come
back: the English version fails the version check.

| Playlist | Correct | Wrong | Unsure | Unmatched | Errors | Error rate | Baseline |
|---|---:|---:|---:|---:|---:|---:|---:|
| Spanish | 50 | 0 | 1 | 0 | 1 | 2.0% | 9.8% |
| English | 173 | 1 | 0 | 0 | 1 | 0.6% | 9.2% |
| Friend's picks (held out, one check) | 143 | 1 | 0 | 0 | 1 | 0.7% | 2.8% |

- Picks changed from the baseline: 12 Spanish, 44 English, 20 held out.
  Music-video or fan-upload picks: 11 -> 3, 32 -> 10, 22 -> 8.
- Judge: off; no overrides, no latency. Picks are in
  `bench/cand1_*_picks.jsonl`. `bench/tools/evaluate.py` rescores them from
  the cache and `bench/labels/picks.tsv` (labels keyed by Spotify track and
  YouTube URL; new picks labelled with the baseline rules).
- Remaining errors:
  - Criminal (Spanish, unsure): YouTube Music's official audio is 4:34 against
    Spotify's 3:52, so only uploads are left. The pick is a lyrics upload 4 s
    longer; uploads with the exact length have fewer views.
  - Whole Lotta Love (English, wrong): Spotify's 369 s track from "The Lost
    Sessions" has no studio match. The pick is the Royal Albert Hall live
    video, whose YouTube Music title has no "live" in it.
  - Northern Attitude (held out, wrong, new): the pick is the version with
    Hozier; Spotify's track is Noah Kahan alone. Fix 1 no longer penalises
    result artists missing from the song. Not fixed here, because it was
    found on the held-out list. Next idea: penalise verified results
    crediting artists the song doesn't have, then test it on Spanish and
    English first.
- Held-out check: 0.7% vs 2.0% and 0.6% on the tuning lists, so no sign of
  overfitting.
- CI: `standard-checks.yml` (MyPy, Pylint 10/10, Black, Isort) passes. The
  Pytest workflow (`tests.yml`) fails as it has on every commit of this
  branch since it was created. Causes: Spotify, Genius and GitHub API calls,
  config-path tests, YTMusic cassettes recorded before the German client, and
  the 10-minute job timeout. Locally the same 12 tests fail before and after
  this change (148 passed now vs 119, counting the new tests). On GitHub the
  failures are the same tests except two Spotify API errors
  (`test_get_search_results`, `test_get_simple_songs`). Those were reached
  only because this run didn't time out, and both pass locally.
