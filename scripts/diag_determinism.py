"""Is the match simulation repeatable on this machine? (CI diagnostic, 2026-10-25)

On the owner's Mac, seed 43 gives identical output every time. On GitHub's Linux runners it did not (COP-11's
distance changed from run to run), so CI's byte-compare tests failed. This script runs the same seed several ways
and reports where the runs first part:

  1. the generator (events) twice in one process,
  2. the tracking twice in one process,
  3. the tracking in two separate processes.

For tracking it names the first frame and player whose position differs. Results are printed and also emitted as
GitHub "::warning" annotations, so they can be read from the run page without opening the log.
Always exits 0: it is a diagnostic, not a gate.

Run: python3 scripts/diag_determinism.py [seed]
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "match-lab"))

from matchlab import generate_match  # noqa: E402
from matchlab.track import dumps  # noqa: E402
from matchlab.tracking import track_match  # noqa: E402


def say(title: str, msg: str) -> None:
    print("%s: %s" % (title, msg))
    if os.environ.get("GITHUB_ACTIONS"):
        print("::warning title=%s::%s" % (title, msg.replace("\n", " | ")))


def sha(obj) -> str:
    return hashlib.sha1(dumps(obj).encode()).hexdigest()[:12]


def first_event_diff(a: dict, b: dict) -> str:
    ea, eb = a["events"], b["events"]
    for i, (x, y) in enumerate(zip(ea, eb)):
        if x != y:
            keys = sorted(k for k in set(x) | set(y) if x.get(k) != y.get(k))
            return "event %d (%s at %s ms) differs in %s" % (i, x.get("type"), x.get("t_ms"), ", ".join(keys))
    return "events equal, lengths %d vs %d" % (len(ea), len(eb))


def first_frame_diff(a: dict, b: dict) -> str:
    hz = a.get("hz", 5)
    best = None  # (frame, entity, axis, va, vb)
    for axis in ("x", "y", "z"):
        for ent, va in a.get(axis, {}).items():
            vb = b.get(axis, {}).get(ent)
            if vb is None:
                return "entity %s missing in one run" % ent
            for f, (p, q) in enumerate(zip(va, vb)):
                if p != q:
                    if best is None or f < best[0]:
                        best = (f, ent, axis, p, q)
                    break
    if best is None:
        return "all frames equal"
    f, ent, axis, p, q = best
    return "first difference at frame %d (%.1f s), %s %s: %s vs %s dm" % (f, f / hz, ent, axis, p, q)


def main() -> int:
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 43
    print("python", sys.version.split()[0], sys.platform)

    m1, m2 = generate_match(seed), generate_match(seed)
    same_gen = sha(m1) == sha(m2)
    say("generator, same process", "identical" if same_gen else first_event_diff(m1, m2))

    t1m, t1 = track_match(generate_match(seed))
    t2m, t2 = track_match(generate_match(seed))
    same_trk = sha(t1) == sha(t2) and sha(t1m) == sha(t2m)
    say("tracking, same process",
        "identical (%s)" % sha(t1) if same_trk
        else "%s; tracked events: %s" % (first_frame_diff(t1, t2), first_event_diff(t1m, t2m)))

    code = ("import sys; sys.path.insert(0, %r)\n"
            "from matchlab import generate_match\nfrom matchlab.track import dumps\n"
            "from matchlab.tracking import track_match\n"
            "m, t = track_match(generate_match(%d))\nsys.stdout.write(dumps(t))\n") % (os.path.join(ROOT, "match-lab"), seed)
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout
    t3 = json.loads(out)
    say("tracking, separate process",
        "identical to this process" if sha(t3) == sha(t1) else first_frame_diff(t1, t3))

    committed = os.path.join(ROOT, "data", "tracking-seed-%d.json" % seed)
    if os.path.exists(committed):
        with open(committed, encoding="utf-8") as fh:
            t0 = json.load(fh)
        say("tracking vs committed data/ (made on the Mac)",
            "identical" if sha(t0) == sha(t1) else first_frame_diff(t0, t1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
