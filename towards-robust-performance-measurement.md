# Towards Robust Performance Measurement

I’m kind of new around here, still learning about how the project works. On the suggestion from Ben Cohen I started contributing code around Swift Benchmark Suite (more benchmarks for `Sequence` protocol along with [support for GYB in benchmarks][pr-gyb]). I’ve filed [SR-4600: Performance comparison should use MEAN and SD for analysis][sr-4600] back in April. After rewriting most of the `compare_perf_test.py`, converting it from [scripting style to OOP module][pr-8991] and adding [full unit test coverage][pr-10035], I’ve been working on improving the robustness of performance measurements with Swift benchmark suite on [my own branch][vk-branch] since the end of June.

[pr-gyb]: https://github.com/apple/swift/pull/8641
[sr-4600]: https://bugs.swift.org/browse/SR-4600
[pr-8991]: https://github.com/apple/swift/pull/8991 "Fix SR-4601 Report Added and Removed Benchmarks in Performance Comparison"
[pr-10035]: https://github.com/apple/swift/pull/10035 "Added documentation and test coverage."
[vk-branch]: http://bit.ly/pali-VK

One of my PRs in the benchmarking area was [blocked](https://github.com/apple/swift/pull/12415) by @gottesmm TK (@Michael_Gottesman), pending wider discussion on swift-dev, I’m guessing because to err on the conservative side is safer than letting me run wild around benchmarks… So the following is *rather long* way to demonstrate what changes to the benchmark suite and our measurement process will, in my opinion, give us more robust results in the future.

First a summary of the status quo, to establish shared understanding of the issues.

## Anatomy of a Swift Benchmark Suite
Compiled benchmark suite consists of 3 binary files, one for each tracked optimization level: `Benchmark_O`, `Benchmark_Onone`, `Benchmark_Osize` (recently changed from `Benchmark_Ounchecked`). I’ll refer to them collectively as `Benchmark_X`. You can invoke them manually or through `Benchmark_Driver`, which is a Python utility that adds more features like log comparison to detect improvements and regressions between Swift revisions.

There are hundreds of microbenchmarks (471 at the time of this writing) that exercise small portions of the language or standard library. They can be executed individually by specifying their name or as a whole suite, usually as part of the pre-commit check done by CI bots using the `Benchmark_Driver`. 

All benchmarks have main performance test function that was historically prefixed with `run_` and is now registered using `BenchmarkInfo` to be recognized by the test harness as part of the suite. The `run_` method takes single parameter `N: Int` —the number of iterations to perform. Each benchmark takes care of this individually, usually by wrapping the main workload in a `for` loop. The `N` is normally determined by the harness so that the **benchmark runs for approximately one-second** per reported sample. It can also be set manually by passing `--num-iters` parameter to the `Benchmark_X` (or `-i` parameter to the `Benchmark_Driver`). The execution of the benchmark for `N` iterations is then timed by the harness, which reports the measured time divided by `N`, making it the **average time per iteration**. This is one sample.

If you also pass the `--num-samples` parameter, the measurements are repeated for specified number of times and the harness also computes and reports the minimum, maximum, mean, standard deviation and median value. `Benchmark_X` reports the measured times in microseconds (**μs**).

*Note that the automatic **scaling** of a benchmark (the computation of `N`) is performed, probably unintentionally, **once per sample**.*

## Issues with the Status Quo
When measuring the performance impact of changes to Swift, the CI bots run the benchmark suite two times: once to get the baseline on the current tip of the tree and again on the branch from the PR. For this, the `Benchmark_Driver` runs set of 334 performance tests (some are **excluded** because they are considered **unstable**) and gathers 20 samples per benchmark for optimized binary and 5 samples per benchmark for unoptimized binary. With ~1s per sample, this results in minimum of **4,6 hours to execute the benchmarks** (not counting project compilation). This means that full benchmarks are requested rather rarely, I guess to not overburden the CI infrastructure. Recently reviewers switched to asking Swift CI to `please smoke benchmark`, which only gathers 3 samples per optimization level, reporting benchmark results in **about 1 hour**.

Performance test results reported by CI on Github often show **false regressions and improvements**, forcing the reviewers to perform frequent judgment calls. Even though there are 137 benchmarks excluded from the pre-commit test because they were considered unstable, the Swift benchmark suite does not appear to be exactly stable...

Sometimes improved compiler optimizations kick in and eliminate main workload of an **incorrectly written benchmark** but nobody notices it for a long stretches of time. Usually the non-zero setup work masks the problem because it prevents measured time from dropping to zero. There is no publicly visible tracking of performance results from the benchmark suite over time that would help prevent this issue either. *`Benchmark_Driver` contains some [legacy code](https://github.com/apple/swift/blob/45a2ae48ceefe6858115371e6eb243b5969f279f/benchmark/scripts/Benchmark_Driver#L234) to publish measurement results to **lnt** server, but it doesn’t appear to be used at the moment*.

When `Benchmark_Driver` runs the `Benchmark_X`, it does so through `time` utility in order to measure memory consumption of the test. It is reported in the log as `MAX_RSS` — maximum resident set size. But this measurement is currently not reported in the benchmark summary from CI on Github and is not publicly tracked, because it is unstable due to the auto-scaling of the measured benchmark loop: the test harness determines the number of iterations to run once per sample depending on the time it took to execute first iteration, the **memory consumption is** [**unstable between samples**](https://github.com/apple/swift/pull/8793#issuecomment-295805969) (not to mention the differences between baseline and branch).

## The Experiment So Far
These are the results from exploring the above mentioned issues performed on an [experimental branch][vk-branch]. All the work so far was done in Python, in the [`Benchmark_Driver`](http://bit.ly/VK-BD) and related [`compare_perf_tests.py`](http://bit.ly/VK-cpt) scripts, without modification of the Swift files in the benchmark suite (*[except a bugfix](https://github.com/apple/swift/pull/12415) to make Benchmark_X run with `--num_iters=1`*). 

`Benchmark_X` supports  `--verbose` option that reports time measured for each sample and the number of iterations used, in addition to the normal benchmark’s report that includes only the summary of minimum, maximum, mean, standard deviation and median values. I’ve extracted log parsing logic from `Benchmark_Driver` into [`LogParser`](http://bit.ly/VK-LogParser) class and taught it to read the verbose output. 

Next I've created [`PerformanceTestSamples`](http://bit.ly/VK-PTS) class that computes the statistics from the parsed verbose output in order to understand what is causing the instability of the benchmarking.

At that point I was visualizing the samples with graphs in Numbers, but it was very cumbersome. So I’ve created [helper script](https://github.com/palimondo/palimondo.github.io/blob/master/diag.py) that exports the samples as JSON and set out to display charts in a web browser, first using [Chartist.js](https://gionkunz.github.io/chartist-js/), later fully replacing it with the [Plotly](https://plot.ly) library.

This dive into visualizations was guided by the [NIST Engineering Statistics Handbook](http://www.itl.nist.gov/div898/handbook/index.htm), the section on [**Exploratory Data Analysis**](http://www.itl.nist.gov/div898/handbook/eda/eda.htm) proved especially invaluable.

### Increased Measurement Frequency and Scaling with Brackets
It is possible to trade `num-iters` for `num-samples` — while maintaining the same ~1 second run time — effectively increasing the measurement frequency. For example, if the auto-scale sets the `N` to 1024, we can get 1 sample to report average value per 1024 iterations, or we can get 1024 samples of raw measured time for single iteration, or anything in-between.

Approximating the automatic scaling of the benchmark to make it run for ~1s like the test harness does in case the `num-iters` parameter is not set (or 0), but with a twist:

* Collect 3 samples with `num-iters=1` (empirically: 1st sample is an outlier, but by the 3rd sample it’s usually in the ballpark of typical value)
* Use the minimum runtime to compute the number of samples that make the benchmark run for ~1s
* Round the number of samples to the nearest power of two

The `Benchmark_X` is then executed with `num-iters=1` and the specified `num-samples` parameter. This results in effective run times around 1 second per benchmark. We can also run with `num-iters=2` and take half as many samples, still maintaining 1s runtime.

Benchmarks can jump between brackets of the number of samples taken on different runs (eg. master branch vs. PR), but measurements are always done with fixed `num-iters` depending on measurement strategy, as described below.

### Monitoring the Environment
Looking at the way we use `time` command invocation of `Benchmark_X` from `Benchmark_Driver` to monitor memory consumption, I noticed that it also reports the number of voluntary and involuntary context switches. So I have started to collect this measure as proxy for sample quality. The number of involuntary context switches (**ICS**) is about 100 per second when my machine is absolutely calm and 1000/s when my machine is busy. The lower bound matches the [anecdotal time slice](https://www.motherboardpoint.com/threads/time-slice-in-os-x.253761/) of 10 ms (10 000 μs) for Mac OS’s scheduler. The number of ICS correlates with the variability of samples.

### Measurement Methodology and Raw Data
My measurements were performed on Late 2008 MacBook Pro with 2.4 GHz Intel Core 2 Duo CPU which is approximately an order of magnitude slower then the Mac Minis used to run benchmarks by CI bots. The recent upgrade of CI infrastructure to use Mac Pros makes this performance gap even bigger. It means that absolute numbers from benchmarks differ compared to those you’ll find in the results from CI on Github, but I believe the overall statistical properties of the dataset are the same.

During my experiments I have noticed that getting a calm machine is very difficult. I had to resort to pretty extreme measures: close all applications (including menu bar apps), quit the Finder(!), disabled Python‘s automatic garbage collection and controlled it manually so that it doesn’t interfere with `Benchmark_O` measurements. To have comparable results during the whole suite measurement, display sleep was also disabled. Getting down to 100 ICS/s required me to also minimize the Terminal window during the measurement. With the Terminal window open, the mean ICS/s was around 300. 

Python’s [`multiprocessing.Pool`](https://docs.python.org/2.7/library/multiprocessing.html#module-multiprocessing.pool) was used to control the amount of contention between concurrently running processes competing for the 2 physical CPU cores. Varying the amount of worker processes that measured multiple benchmarks in parallel provided comparable and relatively constant machine load for the duration of the whole benchmark suite execution.

Intrigued by the variance between various sampling techniques in my initial tests, I did run several different data collection strategies (ascending and descending iteration counts, interleaved or in series) to determine if `--num-iters` is a causal factor behind it. It doesn’t seem to have a direct effect.

The measurements strategies are defined in the helper script [`diag.py`](https://github.com/palimondo/palimondo.github.io/blob/master/diag.py) that uses the [`BenchmarkDriver`](http://bit.ly/VK-BD) to collect and save all the measurements. Benchmark samples are stored in individual JSON files and can be visualized using the [`chart.html`](https://github.com/palimondo/palimondo.github.io/blob/master/chart.html) which fetches the raw data and displays various plots and numerical statistics. Follow the links to explore the complete dataset in web browser yourself.

The complete set of Swift Benchmark Suite measurements collected with a given strategy on a machine with certain level of business are labeled by the letter of alphabet followed by a number of series taken for each benchmark and an optional suffix.

* a - single process, Terminal minimized during measurement
* b - single process
* c - two processes
* d - three processes
* e - four processes

Measurement strategies:
* 10 Series - Collection of 6 `i1` and 4 `i2` for a total of 10 independent one-second runs (executed with `num-iters=1` six times, then with `num-iters=2` four times) 
* 12 Series - Measurements collecting 4 `i1`, 4 `i2` and 4 `i4` runs, for a total of 12 independent one-second benchmark executions (run with `num-iters` = 4, 2, 1, 4, 2, 1, etc.)
* 10R Series - Where R stands for reversed order; measured 5 `i2` runs followed by 5 `i1` runs for a total of 10 one-second benchmark series.

| Series | a | b | c | d | e |
|---|---|---|---|---|---|
| **10** | [a10](chart.html?f=Ackermann+a10.json) | [b10](chart.html?f=Ackermann+b10.json) | [c10](chart.html?f=Ackermann+c10.json) | [d10](chart.html?f=Ackermann+d10.json) | [e10](chart.html?f=Ackermann+e10.json) |
| **12** | [a12](chart.html?f=Ackermann+a12.json) | [b12](chart.html?f=Ackermann+b12.json) | [c12](chart.html?f=Ackermann+c12.json) | [d12](chart.html?f=Ackermann+d12.json) | [e12](chart.html?f=Ackermann+e12.json) |
| **10R** | [a10R](chart.html?f=Ackermann+a10R.json) | [b10R](chart.html?f=Ackermann+b10R.json) | [c10R](chart.html?f=Ackermann+c10R.json) | [d10R](chart.html?f=Ackermann+d10R.json) | [e10R](chart.html?f=Ackermann+e10R.json) |
| **# proc** | **1** | **1** | **2** | **3** | **4** |

The individual series of measurements for a given benchmark are labeled with letters of alphabet after the number of iterations used for the measurement. For example `i4b` is the second measurement performed with iteration count of four. The series table under the main chart is always sorted by ascending iteration count and does not necessarily reflect the order of how the measurements were taken. 

The complete set of Swift Benchmark Suite measurements with varying number of iteration per run, from 1 up, in powers of 2 until the only two samples are collected, are available in the [**iters**](chart.html?f=Ackermann+iters.json) series.

As an ideal baseline for status quo the measurement that collected 4 series of 20 automatically scaled (`num-samples=0`) samples was driven by a [shell script](measure_i0.sh) that saved logs in individual files for later processing is collected in the [**i0** series](chart.html?f=Ackermann+i0.json).

## Analysis
Let’s first examine one fairly typical benchmark.
TK
[1](chart.html?f=ArrayLiteral+iters.json)

<iframe src="http://palimondo.github.com/chart.html?f=ArrayLiteral+iters.json&hide=navigation+plots" name="ArrayLiteral+iters" frameborder="0" width="100%" height="640"></iframe>

All ten series in the chart above represent ~1s of timing benchmark [`ArrayLiteral`](https://github.com/apple/swift/blob/master/benchmark/single-source/ArrayLiteral.swift), with varying number of iterations (denoted by `i#` in the series’ name). This results in progressively less samples (`n` in the table) as the number of iterations averaged in the reported time increases.

TK

On the other hand, the higher iteration counts are averaging over longer stretches of time, therefore including more of the accumulated error. The worst extreme being our status quo, where the reported 1 sample/second includes all the interrupts to the measured process during that time.

TK 

With the decrease of iterations averaged in each sample, their variability rises. This is probably the reason for originally introducing the averaging over multiple iterations in `Benchmark_X` in the first place. At least that’s how I understand @atrick’s [recollection here](https://github.com/apple/swift/pull/8793#issuecomment-297791517).

But the increase in variability is comes from accumulated errors caused by preemptive multitasking. When the operating system’s scheduler interrupts our process in the middle of measurement, the reported sample time also includes the time it took to switch context to another process, its execution and switching back. The frequency and magnitude of these errors varies depending on the overall system load and is outside of our direct control. 

Current measurement system with auto-scaling always **reports the time with cumulative error** of all the interrupts that have occurred during the ~1s of measurement. **This is the root cause of instability** in the reported benchmark improvements and regressions. There are no unstable benchmarks. Our measurement **process is fragile** — easily susceptible to the whims of varying system load. Currently we only attempt to counteract it with brute force, looking for the lowest measured sample gathered in about 20 seconds. We are also looking for an outlier: a minimum, not a typical value! With having just 20 samples overall, we have little indication of their quality. Smoke benchmark with 3 samples has no hard statistical evidence for the reported improvements and regressions.

With the increased sampling frequency, it is possible to detect outliers. On the left side of the scatter plot of individual samples is a [box plot](http://www.itl.nist.gov/div898/handbook/eda/section3/boxplot.htm), which shows the first quartile (**Q1**, the 25th percentile), median (**Med**) and third quartile (**Q3**, 75th percentile) as filled rectangle. This box represents the middle 50% or the “body” of the data, the interquartile range. The whiskers protruding from it represent either the minimum and maximum or the inner fences, which are used to detect outliers based on the interquartile range (**IQR** = Q3 - Q1). In our case, we are concerned about outliers that increase our error, so we will keep the minimum and only use the top inner fence (**TIF** = Q3 + 1.5 * IQR). All samples above this value will be considered **outliers**. 

The mean values are also shown in this box plot as a small horizontal line across the box, if it lies within the “clean” range (<= TIF) or as a circle if it lies above it.

The [scatter plot](http://www.itl.nist.gov/div898/handbook/eda/section3/scatterp.htm) in the middle contains vertical lines denoting the median (solid line), Q1 and Q3 (dotted), mean (dashed) and TIF (dash-dot). 

On the right side of the scatter plot is the vertical [histogram](http://www.itl.nist.gov/div898/handbook/eda/section3/histogra.htm).

TK show chart for a10 series

From the histogram we can see that our measurements are **not normally distributed**, but skewed due to the presence of outliers. This makes the **mean** and **standard deviation** (SD) poor estimates for a [typical value](http://www.itl.nist.gov/div898/handbook/eda/section3/eda351.htm) and its [uncertainity](http://www.itl.nist.gov/div898/handbook/eda/section3/eda356.htm) in our raw dataset. **Median** and **interquartile range** are a more robust measures in this case. All these measures are compared in the table for each series as well as for all samples together. Notice the percentage difference of uncertainty between the IQR (computed here as IQR / Median) and [coefficient of variation](https://en.m.wikipedia.org/wiki/Coefficient_of_variation) (**CV** = SD / Mean).

### Exclude Outliers

To improve the quality and reliability of our measurement process, we can exclude the outlier samples. Filtering the measured data to exclude all samples above the top inner fence from the box plot (Q3 + 1.5 * IQR) yields much cleaner dataset.

TK chart with exclude outliers

Using this rule of thumb to clean our data takes care of the clear outliers. We see the range (**R**) and CV metrics improve. For measurements on a relatively calm machine, this technique is able to almost normalize the measured data: Mean is very close to Median and IQR is comparable to CV.

Aggregating samples from all series improves the robustness of measurement process in a presence of outlier series.

TK characterize the nature of error, susceptibility to contamination (python GC, etc), the need to eliminate the outliers. 

### Exclude Setup Overhead

Some benchmarks need to perform additional setup work before their main workload. Historically, this was dealt with by sizing the main workload so that it dwarfs the setup, making it negligible. Most tests do this by wrapping the main body of work in an inner loop with constant multiplier in addition to the outer loop driven by the `N` variable supplied by the harness. Setup is performed before these loops.

The setup overhead is a systematic measurement error, that can be detected and corrected for, when measuring with multiple `num-iters`. 

TK equation for setup overhead

Following test have setup overhead (with %):

[PR 12404](https://github.com/apple/swift/pull/12404/commits) has added the ability to perform setup and tear down outside of the measured performance test that is so far used by one benchmark.



### Memory Use
Collecting the maximum resident set size from the `time` command gives us a rough estimate of memory used by a benchmark during the measurement. The measured value is in bytes, but with a granularity of a single page (4 KB). When running `Benchmark_O` with nonexistent test 50 times, we establish a minimal baseline value of 2434 pages (9.5 MB) that jumps around between measurements. I guess this is due to varying amount of memory fragmentation the allocator deals with. The range is 13 pages (52KB), i.e. the maximum value seen was 2447 pages (9.56 MB). That is without taking any actual measurements, just instantiating the benchmarking process and processing command line parameters.

The `TypeFlood` benchmark which basically reduces to NOP in the optimized build adds at least additional 113 pages (0.44 MB). That seems to be the memory overhead introduced by the measurement infrastructure.

Rebasing the `MAX_RSS` values measured for our series of benchmarks on the 2547 pages baseline (10 188 KB): 2/3 of benchmarks use less than 25 pages (100 KB). Of the remaining, some 70 benchmarks stay under 200 KB, about 50 tests are in 50-100 pages range (under 400 KB), remaining 52 go above that.

With the exception of 7 benchmarks, all benchmarks have constant memory use independent of the number of measured iterations. I suppose the following benchmarks are written incorrectly, because they vary the memory footprint of the base workload depending on the `N`: `Join`, `MonteCarloE`, `ArraySubscript` and 4 members of the `Observer*` family.

The `Array2D` benchmark has significant memory use range of 7MB (3292 — 5101 pages or 12.9 MB — 19.9 MB)! It creates a 1K by 1K `[[Int]]`, without reserving a capacity. The  pure `Int` storage is at least 8 MB, plus there is some constant overhead per Array. I guess the variation depends on how big contiguous memory regions the allocator gets, while the arrays are growing when `append` is called and they sometimes need to be copied to new region. Though I’m not sure this is the point of the test and it maybe should be rewritten with reserved capacity for stable memory use.

# Corrective Measures
Based on the above analysis I suggest we take following corrective measures:

* Ensure individual benchmarks conform to expected requirements by automating their validation (using `BenchmarkDoctor`):
** Runtime under 2500 μs (with exceptions for individual members of benchmark families)
** Negligible setup overhead (under 5% of runtime)
** Constant memory use independent of iteration count
** Benchmark name is less than or equal to 40 characters, to prevent obscuring results in report tables
* Measure memory use and context switches in Swift by calling `rusage` before 1st and after last sample is taken (abstracted for platform specific implementations)
* Exclude outliers from measured dataset by filtering run times that exceed (Q3 + 1.5 * IQR) (`--exclude-outliers=true` by default)
* Report following statistics for a performance test run:
** Minimum, Q1, Median, Q3, Maximum, Mean, SD, n (number of samples after excluding outliers), number of context switches during measurement, TK ? Cumulative time (for whole measurement)
* Implement parallel benchmarking in `BenchmarkDriver` script to dramatically speed up measurement of the whole benchmark suite.

Other possible improvements:  
* Option to report 20 percentiles in 5% increments (because 10% don’t fall on Q1 and Q3 exactly); compressed in delta format where each successive value is expressed as delta from the previous data point.

# XXX
Current method to reduce variation in the samples is to average a 1s worth of them into the reported result. This achieves reduction of variation at the cost of inflating the true value by a random sampling of -naturally-(not true) distributed error.

TK We also need to significantly lower the workload inside the main loop of most tests, to allow the benchmark driver to call it with high enough frequency in-between time sampling. 
TK The workload inside the main loop should take comparable time to the time quantum assigned by the OS process scheduler to the processes when performing preemptive multitasking. 
TK The point is to be clearly able to distinguish between clean samples and samples that were interrupted by a different process. Empirically, when we can take at least 512 samples per second, the sample distribution is heavily skewed towards the minimum, making it easy to determine the mode.

