### Memory Use
Collecting the maximum resident set size from the `time` command gives us a rough estimate of memory used by a benchmark during the measurement. The measured value is in bytes, but with a granularity of a single page (4 KB). When running `Benchmark_O` with nonexistent test 50 times, we establish a minimal baseline value of 2434 pages (9.5 MB) that jumps around between measurements. I guess this is due to varying amount of memory fragmentation the allocator deals with. The range is 13 pages (52KB), i.e. the maximum value seen was 2447 pages (9.56 MB). That is without taking any actual measurements, just instantiating the benchmarking process and processing command line parameters.

The `TypeFlood` benchmark which basically reduces to NOP in the optimized build adds at least additional 113 pages (0.44 MB). That seems to be the memory overhead introduced by the measurement infrastructure in the parent process that gets reported together.

Rebasing the `MAX_RSS` values measured for our series of benchmarks on the 2547 pages baseline (10 188 KB): 2/3 of benchmarks use less than 25 pages (100 KB). Of the remaining, some 70 benchmarks stay under 200 KB, about 50 tests are in 50-100 pages range (under 400 KB), remaining 52 go above that.

With the exception of 7 benchmarks, all benchmarks have constant memory use independent of the number of measured iterations. I suppose the following benchmarks are written incorrectly, because they vary the memory footprint of the base workload depending on the `N`: `Join`, `MonteCarloE`, `ArraySubscript` and 4 members of the `Observer*` family.

The `Array2D` benchmark has significant memory use range of 7MB (3292 — 5101 pages or 12.9 MB — 19.9 MB)! It creates a 1K by 1K `[[Int]]`, without reserving a capacity. The  pure `Int` storage is at least 8 MB, plus there is some constant overhead per Array. I guess the variation depends on how big contiguous memory regions the allocator gets, while the arrays are growing when `append` is called and they sometimes need to be copied to new region. Though I’m not sure this is the point of the test and it maybe should be rewritten with reserved capacity for stable memory use.

Previous: [Detecting Changes](detecting-changes.md)<br/>
Next: [Corrective Measures](corrective-measures.md)