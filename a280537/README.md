# A280537: a new lower bound a(28) ≥ 57 (no four points in a plane)

**Problem.** [OEIS A280537](https://oeis.org/A280537): the maximum number of points that can be chosen from an n × n × n grid with no four of them in a plane.

**Result.** `a280537_n28_57.txt` gives 57 points in the 28 × 28 × 28 grid {0..27}³, no four of them coplanar. So **a(28) ≥ 57**.

**Previous best known (as of 2026-10-17).**
- The OEIS entry lists terms and lower bounds only up to n = 18.
- Al Zimmermann's 2016 contest "Non-Coplanar Points" covered prime n only (best values there: 66 at n = 29).
- The table in Kudriashov's 2026 note (A280537 configurations, n = 9..29) gives 56 for n = 28, inherited from a(27) ≥ 56 (any configuration in a 27-cube also fits in a 28-cube).

As far as we could find, no 28-cube configuration with more than 56 points had been published.

## Verification
Two independent checks, both included or reproducible:

1. `verify4.py`: for every 4-subset of the 57 points (C(57,4) = 395,010 quadruples), the integer determinant
   det(b−a, c−a, d−a) is nonzero.
   ```
   python3 verify4.py a280537_n28_57.txt
   OK   a280537_n28_57.txt  n=28: 57 points, no four coplanar
   ```
2. Plane-hashing check: each of the C(57,3) = 29,260 triples spans a plane (no collinear triple). Every triple
   gives a different plane (29,260 distinct planes), so no plane contains four of the points.

## How it was found
`search5.c` uses min-conflicts tabu local search for a fixed number of points K. Each grid cell keeps a count of how many
lines (through pairs of chosen points) and planes (through triples of chosen points) pass through it. Adding a cell
with count 0 keeps the set valid. Starting from a greedy valid set, the search repeatedly swaps the
most-conflicted chosen point for the least-conflicted free cell. When it reaches zero conflicts it records the set and tries K+1.
The 57-point set was reached about 9 seconds into a run (`./search5 28 600 1 out.txt`).

The search code was written and run with an AI assistant (Claude) as part of this project.

```
gcc -O3 -o search5 search5.c
./search5 28 600 1 out.txt      # n, seconds, random seed, output file
python3 verify4.py out.txt
```

## Other attempts (10-minute runs, same program)
| n | found | best known |
|---|---|---|
| 20 | 43 | 46 |
| 24 | 50 | 54 |
| 25 | 52 | 54 |
| 26 | 54 | 54 |
| 28 | **57** | 56 |
| 30 | 61 | 66 |
