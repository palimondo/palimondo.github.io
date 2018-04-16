# Towards Robust Performance Measurement
[Pavol Vaskovic](mailto:pali@pali.sk)

This document describes the state of Swift Benchmark Suite around the autumn of 2017 and discusses work to improve the robustness of performance measurements done on [experimental branch][vk-branch] since the end of June 2017.

[vk-branch]: http://bit.ly/pali-VK "voight-kampff"

### Table of Contents
* [Anatomy of the Swift Benchmark Suite](#anatomy-of-the-swift-benchmark-suite)
* [Issues with the Status Quo](#issues-with-the-status-quo)
* [The Experiment So Far](#the-experiment-so-far)
* [Analysis](analysis.md)
* [Exclude Outliers](exclude-outliers.md)
* [Exclude Setup Overhead](exclude-setup-overhead.md)
* [Detecting Changes](detecting-changes.md)
* [Memory Use](memory-use.md)
* [Corrective Measures](corrective-measures.md)

First a summary of the status quo, to establish shared understanding of the issues.

## Anatomy of the Swift Benchmark Suite
Compiled benchmark suite consists of 3 binary files, one for each tracked optimization level: `Benchmark_O`, `Benchmark_Onone`, `Benchmark_Osize` (recently changed from `Benchmark_Ounchecked`). I’ll refer to them collectively as `Benchmark_X`. You can invoke them manually or through `Benchmark_Driver`, which is a Python utility that adds more features like log comparison to detect improvements and regressions between Swift revisions.

There are hundreds of microbenchmarks (471 at the time of this writing) that exercise small portions of the language or standard library. They can be executed individually by specifying their name or as a whole suite, usually as part of the pre-commit check done by CI bots using the `Benchmark_Driver`.

All benchmarks have main performance test function that was historically prefixed with `run_` and is now registered using `BenchmarkInfo` to be recognized by the test harness as part of the suite. The `run_` method takes single parameter `N: Int` —the number of iterations to perform. Each benchmark takes care of this individually, usually by wrapping the main workload in a `for` loop. The `N` is normally determined by the harness so that the **benchmark runs for approximately one second** per reported sample. It can also be set manually by passing `--num-iters` parameter to the `Benchmark_X` (or `-i` parameter to the `Benchmark_Driver`). The execution of the benchmark for `N` iterations is then timed by the harness, which reports the measured time divided by `N`, making it the **average time per iteration**. This is one sample.

If you also pass the `--num-samples` parameter, the measurements are repeated for specified number of times and the harness also computes and reports the minimum, maximum, mean, standard deviation and median value. `Benchmark_X` reports the measured times in microseconds (**μs**).

*Note that the automatic **scaling** of a benchmark (the computation of `N`) is performed, probably unintentionally, **once per sample**.*

## Issues with the Status Quo
When measuring the performance impact of changes to Swift, the CI bots run the benchmark suite two times: once to get the baseline on the current tip of the tree and again on the branch from the PR. For this, the `Benchmark_Driver` runs set of 334 performance tests (some are **excluded** because they are considered **unstable**) and gathers 20 samples per benchmark for optimized binary and 5 samples per benchmark for unoptimized binary. With ~1s per sample, this results in minimum of **4,6 hours to execute the benchmarks** (not counting project compilation). This means that full benchmarks are requested rather rarely, I guess to not overburden the CI infrastructure. Recently reviewers switched to asking Swift CI to `please smoke benchmark`, which only gathers 3 samples per optimization level, reporting benchmark results in **about 1 hour**.

Performance test results reported by CI on Github often show **false regressions and improvements**, forcing the reviewers to perform frequent judgment calls. Even though there are 137 benchmarks excluded from the pre-commit test because they were considered unstable, the Swift benchmark suite does not appear to be exactly stable...

Sometimes improved compiler optimizations kick in and eliminate main workload of an **incorrectly written benchmark** but nobody notices it for a long stretches of time. Usually the non-zero setup work masks the problem because it prevents measured time from dropping to zero. There is no publicly visible tracking of performance results from the benchmark suite over time that would help prevent this issue either. *`Benchmark_Driver` contains some [legacy code](https://github.com/apple/swift/blob/45a2ae48ceefe6858115371e6eb243b5969f279f/benchmark/scripts/Benchmark_Driver#L234) to publish measurement results to **lnt** server, but it doesn’t appear to be used at the moment*.

When `Benchmark_Driver` runs the `Benchmark_X`, it does so through `time` utility in order to measure memory consumption of the test. It is reported in the log as `MAX_RSS` — maximum resident set size. But this measurement is currently not reported in the benchmark summary from CI on Github and is not publicly tracked, because it is unstable due to the auto-scaling of the measured benchmark loop: the test harness determines the number of iterations to run once per sample depending on the time it took to execute first iteration, the **memory consumption is** [**unstable between samples**](https://github.com/apple/swift/pull/8793#issuecomment-295805969) (not to mention the differences between baseline and branch).

## The Experiment So Far
These are the results from exploring the above mentioned issues performed on an [experimental branch][vk-branch]. All the work so far was done in Python, in the [`Benchmark_Driver`](http://bit.ly/VK-BD) and related [`compare_perf_tests.py`](http://bit.ly/VK-cpt) scripts, without modification of the Swift files in the benchmark suite (*[except a bugfix](https://github.com/apple/swift/pull/12415) to make Benchmark_X run with `--num_iters=1`*).

`Benchmark_X` supports `--verbose` option that reports time measured for each sample and the number of iterations used, in addition to the normal benchmark’s report that includes only the summary of minimum, maximum, mean, standard deviation and median values. I’ve extracted log parsing logic from `Benchmark_Driver` into [`LogParser`](http://bit.ly/VK-LogParser) class and taught it to read the verbose output.

Next I've created [`PerformanceTestSamples`](http://bit.ly/VK-PTS) class that computes the statistics from the parsed verbose output in order to understand what is causing the instability of the benchmarking.

At that point I was visualizing the samples with graphs in Numbers, but it was very cumbersome. So I’ve created [helper script](https://github.com/palimondo/palimondo.github.io/blob/master/diag.py) that exports the samples as JSON and set out to display charts in a web browser, first using [Chartist.js](https://gionkunz.github.io/chartist-js/), later fully replacing it with the [Plotly](https://plot.ly) library.

This dive into visualizations was guided by the [NIST Engineering Statistics Handbook](https://www.itl.nist.gov/div898/handbook/index.htm), the section on [**Exploratory Data Analysis**](https://www.itl.nist.gov/div898/handbook/eda/eda.htm) proved especially invaluable.

### Increased Measurement Frequency and Scaling with Brackets
It is possible to trade `num-iters` for `num-samples` — while maintaining the same ~1 second run time — effectively increasing the measurement frequency. For example, if the auto-scale sets the `N` to 1024, we can get 1 sample to report average value per 1024 iterations, or we can get 1024 samples of raw measured time for single iteration, or anything in-between.

Approximating the automatic scaling of the benchmark to make it run for ~1s like the test harness does in case the `num-iters` parameter is not set (or 0), but with a twist:

* Collect 3 samples with `num-iters=1` (empirically: 1st sample is an outlier, but by the 3rd sample it’s usually in the ballpark of typical value)
* Use the minimum runtime to compute the number of samples that make the benchmark run for ~1s
* Round the number of samples to the nearest power of two

The `Benchmark_X` is then executed with `num-iters=1` and the specified `num-samples` parameter. This results in effective run times around 1 second per benchmark. We can also run with `num-iters=2` and take half as many samples, still maintaining 1s runtime. Benchmarks can jump between brackets of the number of samples taken on different runs (eg. master branch vs. PR), but measurements are always done with fixed `num-iters` depending on measurement strategy, as described below. (*Maximum number of gathered samples was capped at 4000, though the display in `chart.html` trims them further to 2000 per series, because the browser wasn’t able to display more than 20000 samples at the same time in reasonable time on my machine.*)

### Monitoring the Environment
Looking at the way we use `time` command invocation of `Benchmark_X` from `Benchmark_Driver` to monitor memory consumption, I noticed that it also reports the number of voluntary and involuntary context switches. So I have started to collect this measure as proxy for sample quality that reflects the load of the system, the amount of contention between competing processes. The number of involuntary context switches (**ICS**) is about 100 per second when my machine is absolutely calm and sometimes reaches over 1000/s when my machine is busy. The lower bound matches the [anecdotal time slice](https://www.motherboardpoint.com/threads/time-slice-in-os-x.253761/) of 10 ms (10 000 μs) for Mac OS’s scheduler. The number of ICS correlates with the variability of samples.

### Measurement Methodology
The measurements were performed in macOS Sierra running on the Late 2008 MacBook Pro with 2.4 GHz Intel Core 2 Duo CPU which is approximately an order of magnitude slower then the Mac Minis used to run benchmarks by CI bots. The recent upgrade of CI infrastructure to use Mac Pros makes this performance gap even bigger. It means that absolute numbers from benchmarks differ compared to those you’ll find in the results from CI on Github, but I believe the overall statistical properties of the dataset are the same.

#### Sampling Strategies
Intrigued by the variance between various sampling techniques in my initial tests, I did run several different data collection strategies (varying ascending and descending iteration counts, interleaved or in series) to determine if `--num-iters` is a causal factor behind it. It doesn’t seem to have a direct effect. Sometimes the later series reach a different stable performance level after few seconds of successive execution. This level can be better or worse. Given this happens after few seconds (3-6), i.e. in the 3rd—6th series measured, I’m not sure if this effect can be attributed to the branch prediction in the CPU.

The sampling strategies are defined in the helper script [`diag.py`](https://github.com/palimondo/palimondo.github.io/blob/master/robust-microbench/diag.py) that uses the [`BenchmarkDriver`](http://bit.ly/VK-BD) to collect and save all the measurements. Benchmark samples are stored in individual JSON files and can be visualized using the [`chart.html`](https://github.com/palimondo/palimondo.github.io/blob/master/chart.html) which fetches the raw data and displays various plots and numerical statistics. Follow the [links below](#raw-data) to explore the complete dataset in web browser yourself.

The individual series of measurements for a given benchmark are labeled with letters of alphabet after the number of iterations used for the measurement. For example `i4b` is the second run of benchmark measurements lasting approximately 1 second, performed with iteration count of four. The series table under the main chart is always sorted by ascending iteration count and does not necessarily reflect the order of how the measurements were taken.

<dl>
<dt><strong>10 Series</strong></dt>
<dd>Collection of 6 `i1` and 4 `i2` series for a total of 10 independent one-second runs (executed with `num-iters=1` six times, then with `num-iters=2` four times).
</dd>
<dt><strong>10R Series</strong></dt>
<dd>Where R stands for reversed order; measured 5 `i2` series followed by 5 `i1` series for a total of 10 one-second benchmark runs.
</dd>
<dt><strong>12 Series</strong></dt>
<dd>Measurements collecting 4 `i1`, 4 `i2` and 4 `i4` runs, interleaved, for a total of 12 independent one-second benchmark executions (run with `num-iters` = 4, 2, 1, 4, 2, 1, etc.).
</dd>
</dl>

#### Controlling the Load
Getting a calm machine during my experiments was very difficult. I had to resort to pretty extreme measures: close all applications (including menu bar apps), quit the Finder(!), disable Python‘s automatic garbage collection and control it manually so that it didn’t interfere with `Benchmark_O`’s measurements.

Producing comparable results during the whole suite measurement was tricky. I have noticed that measurement quality (reflected in very low ICS) mysteriously improved for later benchmarks, once the display went to sleep. I figured out that getting down to 100 ICS/s is possible when you minimize the Terminal window during the measurement for some reason. With the Terminal window open, the mean ICS/s was around 300. To control for this effect, the display sleep was disabled. For the best possible result (the “a series” below) the Terminal window was also minimized.

Python’s [`multiprocessing.Pool`](https://docs.python.org/2.7/library/multiprocessing.html#module-multiprocessing.pool) was used to control the amount of contention between concurrently running processes competing for the 2 physical CPU cores. Varying the amount of worker processes that measured multiple benchmarks in parallel provided comparable and relatively constant machine load for the duration of the whole benchmark suite execution.

Samples in series **a** and **b** had only **1 process** performing the measurements. The samples collected in the **c** series had **2 processes** running benchmarks concurrently and taking the measurements on a 2 core CPU. Series **d** had **3 processes** and series **e** had **4 processes** measuring concurrently running benchmarks competing for the 2 physical CPU cores.

All this is meant to simulate the effect of varying system load, that is outside of our control. For example the CI bots that perform the Swift Benchmark Suite measurements are also running the continuous integration server Jenkins, which uses Java as its runtime environment. We have no control over the Java’s garbage collection that will run concurrently to our benchmark measurements — we have to design our measurement process to be resilient and robust in this environment.

#### Raw Data

The complete set of Swift Benchmark Suite samples collected with a given strategy on a machine with certain level of load is labeled by the letter of alphabet followed by a number of series taken for each benchmark and an optional suffix.

| Series | a | b | c | d | e |
|---:|---|---|---|---|---|
| **10** | [a10](chart.html?b=Ackermann&v=a10) | [b10](chart.html?b=Ackermann&v=b10) | [c10](chart.html?b=Ackermann&v=c10) | [d10](chart.html?b=Ackermann&v=d10) | [e10](chart.html?b=Ackermann&v=e10) |
| **12** | [a12](chart.html?b=Ackermann&v=a12) | [b12](chart.html?b=Ackermann&v=b12) | [c12](chart.html?b=Ackermann&v=c12) | [d12](chart.html?b=Ackermann&v=d12) | [e12](chart.html?b=Ackermann&v=e12) |
| **10R** | [a10R](chart.html?b=Ackermann&v=a10R) | [b10R](chart.html?b=Ackermann&v=b10R) | [c10R](chart.html?b=Ackermann&v=c10R) | [d10R](chart.html?b=Ackermann&v=d10R) | [e10R](chart.html?b=Ackermann&v=e10R) |

The *a* and *b* series both run in 1 process, except that for the *a* series measurement the Terminal window was minimized.

The number of involuntary context switches (ICS) is just a proxy for machine load. When we normalize the ICS per second, this measure for a series in a given system load level is almost normally distributed. The *a* series is very tightly packed with mean value at 90 ICS/s (±10). The *b* series has two [modes](https://en.wikipedia.org/wiki/Mode_%28statistics%29): one sharp peak at 120 ICS/s (±10) and another wide peak at 350 ICS/s (±80). The ICS spread in *c* series is very wide with mode at 700 (±280).

| Series | a | b | c | d | e |
|---:|:---:|:---:|:---:|:---:|:---:|
| **Number of <br> processes** | 1 | 1 | 2 | 3 | 4 |
| **Mean runtime** <br> (s/benchmark) | 1 | 1 | 1 | 1.5 | 2 |
| **ICS Mode** | 90 | 120 <br> 350 | 700 | 500 | 380 |
| **ICS Standard <br> Deviation** | ±10 | ±10 <br> ±80 | ±280 | ±190 | ±140 |

Even on a fully saturated processor, the number of context switches does not often exceed 1000 ICS during one benchmark measurement, but the interruptions get longer. This is why the ICS values normalized to one second gets lower as the mean runtime increases for series *d* and *e*.

Another set of samples with varying number of iterations per run, from 1 up, in powers of 2 until the only two samples are collected, are available in the [**iters**](chart.html?b=Ackermann&v=iters) series. The machine load during this measurement was roughly equivalent to the *c* series above (Mode 600 ICS/s, ±200).

As an ideal baseline for the status quo, the collection of 4 series with 20 automatically scaled (`num-samples=0`) samples was driven by a [shell script](measure_i0.sh) that saved logs in individual files for later processing is collected in the [**i0** series](chart.html?f=Ackermann+i0.json). This is roughly equivalent to 4 whole benchmark suite executions on a machine with load corresponding to the *a* series above.

Remember that *a* level of system load is never attainable on CI bots running Java, even if we take care of macOS system’s background processes like (Spotlight indexing and Time Machine backups), but is used here to establish the rough equivalence between the ideal version of status quo and proposed changes to the measurement process.

If you’d like to perform your own analysis, the complete dataset is available for download as a single archive [sbs_dataset_1.0.zip](sbs_dataset_1.0.zip).

Next: [Analysis](analysis.md)
