# Judge benchmark data (first round, Mac with 8 GB, Kev-0.8B)

- `base_*` runs: before the fixes in this branch. `fix1_*` runs: after them.
  `es` = Spanish playlist 5VskdvX3OlGVAHhn1jgoAm (51 songs), `en` = English
  playlist 4PniezFG51rrLjQhkWqHsC (174 songs). `t07`/`t09` = judge threshold.
- `*_requests.jsonl`: every state and question sent to Kev, with its answers.
  `tools/replay.py` replays them against another model or question design
  without searching again.
- `labels/`: hand labels of spotDL's picks. The Spanish labels were redone for
  `fix1` (see `verdicts_es.json`). A pick is correct if it is the same song,
  artist and version, with audio within about 5 s. Music videos that differ by
  more than that are marked wrong or unsure until someone listens to them.

Results: Spanish went from 33/51 correct (65%) to 47/51 (92%) from the spotDL
fixes alone. Kev-0.8B changed no picks at any threshold: "none" usually had the
highest probability, and forced picks followed candidate position, not content.
