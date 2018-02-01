# Towards Robust Performance Measurement

I’m kind of new around here, still learning about how the project works. On the suggestion from Ben Cohen I started contributing code around Swift Benchmark Suite (more benchmarks for `Sequence` protocol along with [support for GYB in benchmarks][pr-gyb]). I’ve filed [SR-4600: Performance comparison should use MEAN and SD for analysis][sr-4600] back in April. After rewriting most of the `compare_perf_test.py`, converting it from [scripting style to OOP module][pr-8991] and adding [full unit test coverage][pr-10035], I’ve been working on improving the robustness of performance measurements with Swift benchmark suite on [my own branch][vk-branch] since the end of June.

[pr-gyb]: https://github.com/apple/swift/pull/8641
[sr-4600]: https://bugs.swift.org/browse/SR-4600
[pr-8991]: https://github.com/apple/swift/pull/8991 "Fix SR-4601 Report Added and Removed Benchmarks in Performance Comparison"
[pr-10035]: https://github.com/apple/swift/pull/10035 "Added documentation and test coverage."
[vk-branch]: http://bit.ly/pali-VK

One of my PRs in the benchmarking area was blocked by @mgottesmann, pending wider discussion on swift-dev, I’m guessing because to err on the conservative side is safer than letting me run wild around benchmarks… So the following is *rather long* way to demonstrate what changes to the benchmark suite and our measurement process will give us more robust results in the future.

First a summary of the status quo, to establish shared understanding of the issues.

## Anatomy of a Swift Benchmark Suite
Compiled benchmark suite consist of 3 binary files, one for each tracked optimization level: `Benchmark_O`, `Benchmark_Onone`, `Benchmark_Osize` (recently changed from `Benchmark_Ounchecked`). I’ll refer to them collectively as `Benchmark_X`. You can invoke them manually or through `Benchmark_Driver`, which is a Python utility that adds more features, for example log comparison to detect improvements and regressions between Swift revisions.

There are hundreds of microbenchmarks (471 at the time of this writing) that exercise small portions of the language or standard library. They can be executed individually by specifying their name or as a whole suite, usually as part of the pre-commit check done by CI bots using the `Benchmark_Driver`. 

All benchmarks have main performance test function that was historically prefixed with `run_` and is now registered using `BenchmarkInfo` to be recognized by the test harness as part of the suite. The run method takes single `Int` parameter `N` representing number of iterations to perform. This is normally determined by the harness so that the benchmark runs for approximately one second per sample. It can also be set manually by passing `--num-iters` parameter to the `Benchmark_X` (or `-i` parameter to the `Benchmark_Driver`).

The execution of the benchmark for `N` iterations is then timed by the harness, which reports the measured time divided by `N`, making it the *average time per iteration*. This is one sample.

If you also pass the `--num-samples` parameter, the measurements are repeated for specified number of times and the harness computes and reports the minimum, maximum, mean, standard deviation and median value. `Benchmark_X` reports the measured times in microseconds (**μs**).

*Note that the automatic scaling of a benchmark (the computation of `N`) is performed, probably unintentionally, once per sample*.

## Issues with the Status Quo
When measuring the performance impact of changes to Swift, the CI bots run the benchmark suite two times: once to get the baseline on the current tip of the tree and again on the branch from the PR. For this, the `Benchmark_Driver` runs set of 334 performance tests (some are excluded because they are considered *unstable*) and gathers 20 samples per benchmark for optimized binary and 5 samples per benchmark for unoptimized binary. With ~1s per sample, this results in minimum of **4,6 hours to execute the benchmarks** (not counting project compilation). This means that full benchmarks are requested rather rarely, I guess to not overburden the CI infrastructure. Recently reviewers switched to asking `please smoke benchmark`, which only gathers 3 samples per optimization level, reporting benchmark results in **about 1 hour**.

Performance tests results reported by CI on Github often show **false regressions and improvements**, forcing the reviewers to perform frequent judgment calls. Even though there are 137 benchmarks excluded from the pre-commit test because they were considered unstable, the Swift benchmark suite does not appear to be exactly stable.

Sometimes improved compiler optimizations kick in and eliminate main workload of an **incorrectly written benchmark** but nobody notices it for a long stretches of time. Usually the non-zero setup work masks the problem because it prevents measured time from dropping to zero. There is no publicly visible tracking of performance results from the benchmark suite over time that would help prevent this issue either.

When `Benchmark_Driver` runs the `Benchmark_X`, it does so through `time` utility in order to **measure memory consumption** of the test. It is reported in the log as `MAX_RSS` — maximum resident set size. But this measurement is currently not reported in the benchmark summary from CI on Github and is not publicly tracked, because it is unstable due to the auto-scaling of the measured benchmark loop: the test harness determines the number of iterations to run once per sample depending on the time it took to execute first iteration, the **memory consumption is unstable between samples** (not to mention the differences between baseline and branch).

## The Experiment So Far
Results of exploring the above issues performed on an [experimental branch][vk-branch] follow. All the work so far was done in Python, in the [`Benchmark_Driver`](http://bit.ly/VK-BD) and related [`compare_perf_tests.py`](http://bit.ly/VK-cpt) scripts, without modification of the Swift files in the benchmark suite. 

I’ve extracted log parsing logic into [`LogParser`](http://bit.ly/VK-LogParser) class and taught it to read the `--verbose` output from `Benchmark_X`. The verbose mode reports time measured for each sample and the number of iterations used, in addition to the normal benchmark’s report that includes only the summary of minimum, maximum, mean, standard deviation and median values.

Next I've created [`PerformanceTestSamples`](http://bit.ly/VK-PTS) class that computes the statistics from the parsed `--verbose` output in order to understand what is causing the instability of the benchmarking.

At that point I was visualizing the samples with graphs in Numbers, but it was very cumbersome. So I’ve created helper script that exports the samples as JSON and set out to display charts in a web browser, first using [Chartist.js](https://gionkunz.github.io/chartist-js/), later fully replacing it with [Plotly](https://plot.ly) library.

The diving into the visualizations of measured data was guided by the [NIST Engineering Statistics Handbook](http://www.itl.nist.gov/div898/handbook/index.htm), specifically the section on [Exploratory Data Analysis](http://www.itl.nist.gov/div898/handbook/eda/eda.htm) proved invaluable.

In the following I’ll be presenting benchmark sample visualizations and statistical graphics from [`chart.html`](https://github.com/palimondo/palimondo.github.io/blob/master/chart.html). You can click on the links to explore the raw and filtered data yourself in the web browser. Note that my measurements were performed on Late 2008 MacBook Pro with 2.4 GHz Intel Core 2 Duo CPU which is approximately an order of magnitude slower then the Mac Minis used to run benchmarks by CI bots. The recent updgrade of CI infrastructure to use Mac Pros makes this performance gap even bigger.

### Scaling within Brackets
I have done several runs of the whole suite with different parameters for the `Benchmark_X`. First I have tried to partially approximate the automatic scaling of the benchmark to make it run for ~1s like the test harness does in case the `--num-iters` parameter is not set (or set to 0), but with a twist:

* Collect 3 samples with `--num-iters=1` (empirically: 1st sample is very often an outlier, but by the 3rd sample it’s usually in the ballpark of typical value)
* Use the minimum runtime to compute number of iterations to make the performance test run for ~1s
* Round the number of iterations up to the nearest power of two

This results in effective run times around 1 second per benchmark, but the benchmarks are grouped into more stable bins that allow for easier comparison between runs. It eliminates one source of measurement noise caused by the auto-scaling of the benchmarks — varying number of iterations per sample that was causing unstable and non-deterministic memory consumption depending on how many other processes were interfering with the measurements.

### Increase Measurement Frequency
It is possible to trade `num-iters` for `num-samples` — while maintaining the same ~1 second run time — effectively increasing the measurement frequency. For example, if the auto-scale sets the `N` to 1024, we can get 1 sample to report average value per 1024 iterations, or we can get 1024 samples of raw measured time for single iteration! Or anything in between: [1](chart.html?f=ArrayLiteral+iters.json)

<iframe src="chart.html?f=ArrayLiteral+iters.json&hide=navigation+plots" name="ArrayLiteral+iters" frameborder="0" width="100%" height="640"></iframe>

All the ten series in the chart above represent ~1s of timing benchmark [`ArrayLiteral`](https://github.com/apple/swift/blob/master/benchmark/single-source/ArrayLiteral.swift), with varying number of iterations (denoted by `i#` in the series’ name). This results in progressively less samples (`n` in the table) as the number of iterations averaged in the reported time increases.

With the decrease of iterations averaged in each sample, their variability rises. This is probably the reason for introducing the averaging over multiple iterations in the first place. These high values are errors caused by preemptive multitasking. When the operating system’s scheduler interrupts our process in the middle of measurement, the reported sample time additionally also includes the time it took to switch context to another process, its execution during the allotted time slice and switching back. The frequency and magnitude of these errors varies depending on the overall system load. 

Our current measurement system with auto-scaling therefore always reports the time with cumulative error of all the interrupts that have occurred during the ~1s of measurement. This is the root cause of instability in the reported benchmark improvements and regressions. Our measurement process is fragile — easily susceptible to the whims of varying system load. We attempt to counteract it with brute force, looking for the lowest measured sample gathered in about 20 seconds. We are looking for an outlier: a minimum. It is not a typical value!

With having just 20 samples overall, we have little indication of their quality. They are too coarse. We don’t really know how representative they are. Having more samples allows us to use statistical methods to improve the quality of our measurements.

TK random vs. systematic error

### Exclude Outliers

TK characterize the nature of error, susceptibility to contamination (python GC, etc), the need to eliminate the outliers. 

Finer granularity sampling revealed two other source of instability.


### Exclude Setup Overhead

Some benchmarks need to perform additional setup work before their main workload. Historically, this was dealt with by sizing the main workload so that it dwarfs the setup, making it negligible. Most tests do this by wrapping the main body of work in an inner loop with constant multiplier in addition to the outer loop driven by the `N` variable supplied by the harness. Setup is performed before these loops. [PR 12404](https://github.com/apple/swift/pull/12404/commits) has added the ability to perform setup and tear down outside of the measured performance test that is so far used by one benchmark.

TK setup work, context switching

Sample with finer granularity, so that we can exclude outliers. These measurement errors are caused by context switching between processes and were previously always accumulated into the reported result. We also need to significantly lower the workload inside the main loop of most tests, to allow the benchmark driver to call it with high enough frequency in-between time sampling. The workload inside the main loop should take comparable time to the time quantum assigned by the OS process scheduler to the processes when performing preemptive multitasking. The point is to be clearly able to distinguish between clean samples and samples that were interrupted by a different process. Empirically, when we can take at least 512 samples per second, the sample distribution is heavily skewed towards the minimum, making it easy to determine the mode.


# XXX
Current method to reduce variation in the samples is to average a 1s worth of them into the reported result. This achieves reduction of variation at the cost of inflating the true value by a random sampling of -naturally-(not true) distributed error.

