"""Independent checker for no-four-coplanar: every quadruple's 3x3 determinant must be nonzero."""
import sys
from itertools import combinations

def check(path):
    lines = [l.split() for l in open(path) if l.strip() and not l.startswith("#")]
    n, k = map(int, lines[0][:2])
    pts = [tuple(map(int, t[:3])) for t in lines[1:]]
    assert len(pts) == k, "count mismatch"
    assert len(set(pts)) == k, "duplicate points"
    assert all(0 <= c < n for p in pts for c in p), "point outside grid"
    for a, b, c, d in combinations(pts, 4):
        u = (b[0]-a[0], b[1]-a[1], b[2]-a[2]); v = (c[0]-a[0], c[1]-a[1], c[2]-a[2]); w = (d[0]-a[0], d[1]-a[1], d[2]-a[2])
        det = u[0]*(v[1]*w[2]-v[2]*w[1]) - u[1]*(v[0]*w[2]-v[2]*w[0]) + u[2]*(v[0]*w[1]-v[1]*w[0])
        if det == 0:
            return False, f"coplanar: {a} {b} {c} {d}"
    return True, f"n={n}: {k} points, no four coplanar"

if __name__ == "__main__":
    for p in sys.argv[1:]:
        ok, msg = check(p)
        print(("OK   " if ok else "FAIL ") + p + "  " + msg)
