# A280537: a 57-point configuration for n = 28 (no four points in a plane)

**My decision.**
I started this project because I wanted to become someone who solves hard or unsolved problems with AI. For my first attempt I tried the no-three-in-line problem, but even after trying many different cases and methods I did not succeed. So I decided to switch to a different problem from the list of problems I had set out at the beginning, and I chose this one. When the result came out, I cross-checked it again on my own MacBook to confirm it.

What I took away from this challenge is that I should keep trying to use AI to work on the world’s problems that are still not fully solved. AI is a useful enough tool to make these attempts possible, and I think it should be used efficiently.

**Problem.** [OEIS A280537](https://oeis.org/A280537): the maximum number of points that can be chosen from an n × n × n grid with no four of them in a plane.

**Result.** `a280537_n28_57.txt` gives 57 points in the 28 × 28 × 28 grid {0..27}³, no four of them coplanar. This shows a(28) ≥ 57, but **this is not a new lower bound** (see the correction below).

**Correction (2026-10-17).** I first wrote that this was a new lower bound, because I thought the previous best for n = 28 was 56. That was wrong. Al Zimmermann's 2016 contest "Non-Coplanar Points" reports 66 points for n = 29. Any plane x = const can hold at most 3 points, so removing the three outer layers x = 28, y = 28 and z = 28 from a 66-point configuration removes at most 9 points and leaves at least 57 points in the 28 × 28 × 28 grid. So a(28) ≥ 57 already follows from the known n = 29 result. A real improvement would need at least 58 points, and possibly more, depending on the n = 29 configuration, which I have not seen.

- The OEIS entry lists terms and lower bounds only up to n = 18.
- Al Zimmermann's contest results: https://azspcs.com/Contest/Tetrahedra/FinalReport

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
   ```
3. Re-checked independently on the author's own MacBook Air (2026-10-17):
   `OK a280537_n28_57.txt n=28: 57 points, no four coplanar`.

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
