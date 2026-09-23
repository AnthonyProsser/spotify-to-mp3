"""Compare spotDL's pick with the current album penalty vs. no penalty when
durations match within 2s. Searches are cached, so both variants see the same results."""
import csv, sys, json
import spotdl.utils.matching as M
from spotdl.providers.audio.ytmusic import YouTubeMusic
from spotdl.types.song import Song
from spotdl.utils.config import DEFAULT_CONFIG
from spotdl.utils.spotify import SpotifyClient
from spotdl.utils.search import reinit_song

SpotifyClient.init(client_id=DEFAULT_CONFIG["client_id"], client_secret=DEFAULT_CONFIG["client_secret"])
orig_album = M.calc_album_match
def new_album(song, result):
    if result.duration and abs(song.duration - result.duration) <= 2:
        return 100.0
    return orig_album(song, result)

p = YouTubeMusic()
rcache, vcache = {}, {}
orig_get_results, orig_get_views = p.get_results, p.get_views
p.get_results = lambda q, **kw: rcache.setdefault((q, json.dumps(kw, sort_keys=True)), None) or rcache.__setitem__((q, json.dumps(kw, sort_keys=True)), orig_get_results(q, **kw)) or rcache[(q, json.dumps(kw, sort_keys=True))]
def views(url):
    if url not in vcache: vcache[url] = orig_get_views(url)
    return vcache[url]
p.get_views = views

for path in sys.argv[1:]:
    for r in csv.DictReader(open(path, encoding="utf-8")):
        for attempt in range(3):
            try:
                song = reinit_song(Song.from_url(r["spotify_url"]))
                M.calc_album_match = orig_album; a = p.search(song)
                M.calc_album_match = new_album; b = p.search(song)
                break
            except Exception as e:
                a = b = f"ERR {e}"[:80]
        flag = "CHANGED" if a != b else "same"
        print(f"{flag}\t{r['song']}\t{a}\t{b}", flush=True)
