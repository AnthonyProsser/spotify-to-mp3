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
