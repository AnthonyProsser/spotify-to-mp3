# Goal brief: cut spotDL's wrong-match rate

## Playlists
- Spanish (51 songs): 5VskdvX3OlGVAHhn1jgoAm
- English (174 songs): 4PniezFG51rrLjQhkWqHsC
- Friend's picks (held out): 0ADNLtVRNIEIvLNNqxykGG

Tune on Spanish and English only. Run the held-out playlist for the baseline,
then again only to check a finished candidate. If it does much worse than the
other two, the change is overfitted.

## Baseline so far (first round, on this branch's current code)
- Spanish: 47 correct, 2 wrong (La Bicicleta, Bailar: music videos picked
  over official audio), 2 unsure (Criminal, Acróstico). Error is 2-4 of 51
  (4-8%).
- English: only partly labelled. At least 2 wrong (Whole Lotta Love is a live
  version; Great Balls of Fire is 101 s against 111 s) and about 6-8 unsure
  music videos or edits (e.g. Don't Stop Me Now, Play The Game, Paranoid, Fat
  Bottomed Girls, Smooth Criminal as a lyrics upload). Roughly 1-6% of 174.
- Friend's playlist: not measured yet.

The first job is to label all three playlists fully and fix this baseline.
Count unsure picks as errors until they have been listened to.

## Known causes (these are observations, not decided fixes)
- The album-mismatch penalty in `spotdl/utils/matching.py`. Spotify lists
  compilations and remasters where YTMusic lists the original album. That
  pushes a verified official audio below a music video that has no album.
- The view-count bonus in `get_best_result` favours music videos, which may
  have intros.
- Official audio gets the early return only if it scores 80 or more.
- Repeated YTMusic searches can return different results.
- The judge's 5 candidates often don't include the right answer.
- Kev-0.8B changed no picks. "None" usually won, and its forced picks followed
  list position. Kev-4B and 9B are untested.

## Ideas to test (none of them is proven; measure each one)
- Prefer verified official audio when its title, artist and duration match.
- Soften the album penalty, or drop it when the duration matches. A first try
  at this broke Waka Waka by picking the English version, so language and
  version (live, edit, remaster) must stay protected.
- Always include the official audio among the judge's candidates.
- Shuffle the candidates, or ask Kev yes or no about each one, to remove
  position bias.
- Use Kev only to verify spotDL's pick, or only on close calls.
- Try more search queries: title plus album, the ISRC, the artist's Topic
  channel.
- Keep the judge off by default if it never beats plain spotDL.

## Tools and data
- `bench/*_requests.jsonl` holds every request sent to Kev. Replay them
  against another model or question design with `tools/replay.py`, with no new
  searches.
- `labels/` holds the first labels. A pick is correct if it is the same song,
  artist and version. A length difference alone doesn't prove it is a
  different recording, because videos add intros.
- Cache search results and yt-dlp metadata (`download=False`) to disk. Score
  experiments from the cache so YouTube doesn't rate-limit you.

## Rules
- No per-song special cases or hardcoded video IDs.
- Every code change gets a unit test, and the CI checks in
  `.github/workflows/standard-checks.yml` must pass.
- Commit each real improvement to `claude/keen-newton-54hz90` and push. End
  each commit message with
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Never push to
  master.
- Don't use the user's cookies or YouTube account.
- Log every experiment in `bench/EXPERIMENTS.md`: the change, then correct,
  wrong, unsure and unmatched counts per playlist, then the judge's overrides
  and its latency.
- List unsure cases with both YouTube links in `bench/listen.md`. The user's
  answers there are final.
