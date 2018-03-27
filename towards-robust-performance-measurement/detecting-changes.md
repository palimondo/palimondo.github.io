## Detecting Changes
The way we detect if benchmarks have improved or regressed during is implemented in [`compare_perf_tests.py`](https://github.com/apple/swift/blob/master/benchmark/scripts/compare_perf_tests.py). It takes the minimum runtime for each benchmark measured from the two compared branches and if their difference is more than `delta_threshold` parameter (defaults to 5%), they are reported as an improvement or a regression. If the ranges (min, max) for compared benchmarks overlap, they are flagged with a `?` in the report. Given that range is very sensitive to outliers, almost all changes are flagged with `?`. 



Previous: [Exclude Setup Overhead](exclude-setup-overhead.md)<br/>
Next: [Memory Use](memory-use.md)