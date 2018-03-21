# Towards Robust Performance Measurement

I’m kind of new around here, still learning about how the project works. On the suggestion from Ben Cohen I started contributing code around Swift Benchmark Suite (more benchmarks for `Sequence` protocol along with [support for GYB in benchmarks](https://github.com/apple/swift/pull/8641)). I’ve filed [SR-4600][sr-4600] back in April of 2017. After rewriting most of the `compare_perf_test.py`, converting it from [scripting style to OOP module][pr-8991] and adding [full unit test coverage][pr-10035], I’ve been working on improving the robustness of performance measurements with Swift benchmark suite on [my own branch][vk-branch] since the end of June.

[sr-4600]: https://bugs.swift.org/browse/SR-4600 "Performance comparison should use MEAN and SD for analysis"
[pr-8991]: https://github.com/apple/swift/pull/8991 "Fix SR-4601 Report Added and Removed Benchmarks in Performance Comparison"
[pr-10035]: https://github.com/apple/swift/pull/10035 "Added documentation and test coverage."

One of my PRs in the benchmarking area was [blocked](https://github.com/apple/swift/pull/12415) by @gottesmm TK (@Michael_Gottesman), pending wider discussion on swift-dev, I’m guessing because to err on the conservative side is safer than letting me run wild around benchmarks… So the linked document is *rather long* way to demonstrate what changes to the benchmark suite and our measurement process will, in my opinion, give us more robust results in the future.

I apologize that the report deals with state of Swift Benchmark Suite from autumn 2018, keeping the tree up to date once the commits I was depending required lengthy manual conflict resolution I gave up on that and kept focusing on the experiment, rather than futile chase of the tip of the tree…

----

This document describes the state of Swift Benchmark Suite around the autumn of 2017 and discusses work to improve the robustness of performance measurements done on [experimental branch][vk-branch] since the end of June 2017.

[vk-branch]: http://bit.ly/pali-VK "voight-kampff"

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

`Benchmark_X` supports `--verbose` option that reports time measured for each sample and the number of iterations used, in addition to the normal benchmark’s report that includes only the summary of minimum, maximum, mean, standard deviation and median values. I’ve extracted log parsing logic from `Benchmark_Driver` into [`LogParser`](http://bit.ly/VK-LogParser) class and taught it to read the verbose output. 

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
Looking at the way we use `time` command invocation of `Benchmark_X` from `Benchmark_Driver` to monitor memory consumption, I noticed that it also reports the number of voluntary and involuntary context switches. So I have started to collect this measure as proxy for sample quality that reflects the load of the system, the amount of contention between competing processes. The number of involuntary context switches (**ICS**) is about 100 per second when my machine is absolutely calm and sometimes reaches over 1000/s when my machine is busy. The lower bound matches the [anecdotal time slice](https://www.motherboardpoint.com/threads/time-slice-in-os-x.253761/) of 10 ms (10 000 μs) for Mac OS’s scheduler. The number of ICS correlates with the variability of samples.

### Measurement Methodology
The measurements were performed in macOS Sierra running on the Late 2008 MacBook Pro with 2.4 GHz Intel Core 2 Duo CPU which is approximately an order of magnitude slower then the Mac Minis used to run benchmarks by CI bots. The recent upgrade of CI infrastructure to use Mac Pros makes this performance gap even bigger. It means that absolute numbers from benchmarks differ compared to those you’ll find in the results from CI on Github, but I believe the overall statistical properties of the dataset are the same.

#### Sampling Strategies
Intrigued by the variance between various sampling techniques in my initial tests, I did run several different data collection strategies (varying ascending and descending iteration counts, interleaved or in series) to determine if `--num-iters` is a causal factor behind it. It doesn’t seem to have a direct effect. Sometimes the later series reach a different stable performance level after few seconds of successive execution. This level can be better or worse. Given this happens after few seconds (3-6), i.e. in the 3rd—6th series measured, I’m not sure if this effect can be attributed to the branch prediction in the CPU.

The sampling strategies are defined in the helper script [`diag.py`](https://github.com/palimondo/palimondo.github.io/blob/master/diag.py) that uses the [`BenchmarkDriver`](http://bit.ly/VK-BD) to collect and save all the measurements. Benchmark samples are stored in individual JSON files and can be visualized using the [`chart.html`](https://github.com/palimondo/palimondo.github.io/blob/master/chart.html) which fetches the raw data and displays various plots and numerical statistics. Follow the [links below](#raw-data) to explore the complete dataset in web browser yourself.

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
| **10** | [a10](chart.html?f=Ackermann+a10.json) | [b10](chart.html?f=Ackermann+b10.json) | [c10](chart.html?f=Ackermann+c10.json) | [d10](chart.html?f=Ackermann+d10.json) | [e10](chart.html?f=Ackermann+e10.json) |
| **12** | [a12](chart.html?f=Ackermann+a12.json) | [b12](chart.html?f=Ackermann+b12.json) | [c12](chart.html?f=Ackermann+c12.json) | [d12](chart.html?f=Ackermann+d12.json) | [e12](chart.html?f=Ackermann+e12.json) |
| **10R** | [a10R](chart.html?f=Ackermann+a10R.json) | [b10R](chart.html?f=Ackermann+b10R.json) | [c10R](chart.html?f=Ackermann+c10R.json) | [d10R](chart.html?f=Ackermann+d10R.json) | [e10R](chart.html?f=Ackermann+e10R.json) |

The *a* and *b* series both run in 1 process, except that for the *a* series measurement the Terminal window was minimized. 

The number of involuntary context switches (ICS) is just a proxy for machine load. When we normalize the ICS per second, this measure for a series in a given system load level is almost normally distributed. The *a* series is very tightly packed with mean value at 90 ICS/s (±10). The *b* series has two [modes](https://en.wikipedia.org/wiki/Mode_%28statistics%29): one sharp peak at 120 ICS/s (±10) and another wide peak at 350 ICS/s (±80). The ICS spread in *c* series is very wide with mode at 700 (±280).

| Series | a | b | c | d | e |
|---:|:---:|:---:|:---:|:---:|:---:|
| **Number of <br> processes** | 1 | 1 | 2 | 3 | 4 |
| **Mean runtime** <br> (s/benchmark) | 1 | 1 | 1 | 1.5 | 2 |
| **ICS Mode** | 90 | 120 <br> 350 | 700 | 500 | 380 |
| **ICS Standard <br> Deviation** | ±10 | ±10 <br> ±80 | ±280 | ±190 | ±140 |

Even on a fully saturated processor, the number of context switches does not often exceed 1000 ICS during one benchmark measurement, but the interruptions get longer. This is why the ICS values normalized to one second gets lower as the mean runtime increases for series *d* and *e*.

Another set of samples with varying number of iterations per run, from 1 up, in powers of 2 until the only two samples are collected, are available in the [**iters**](chart.html?f=Ackermann+iters.json) series. The machine load during this measurement was roughly equivalent to the *c* series above (Mode 600 ICS/s, ±200).

As an ideal baseline for the status quo, the collection of 4 series with 20 automatically scaled (`num-samples=0`) samples was driven by a [shell script](measure_i0.sh) that saved logs in individual files for later processing is collected in the [**i0** series](chart.html?f=Ackermann+i0.json). This is roughly equivalent to 4 whole benchmark suite executions on a machine with load corresponding to the *a* series above. 

Remember that *a* level of system load is never attainable on CI bots running Java, even if we take care of macOS system’s background processes like (Spotlight indexing and Time Machine backups), but is used here to establish the rough equivalence between the ideal version of status quo and proposed changes to the measurement process.

## Analysis
To understand what’s behind the mean value reported by our status quo measurement process, we’ll examine single benchmark with the newly increased sampling frequency. All eleven series of samples in the chart below represent ~1s (0.7–0.8s in this case) of timing the benchmark [`Calculator`](https://github.com/apple/swift/blob/master/benchmark/single-source/Calculator.swift), with varying number of iterations. This yields progressively less samples (`n` in the table) as the number of iterations averaged in the reported time increases (denoted by `i#` in the series’ name). Remember that our current measurement process reports only the mean value (**x̅** column) from 1 second of execution for each of the series. 

Notice the differences between [mean](https://en.wikipedia.org/wiki/Mean#Statistical_location) and [median](https://en.wikipedia.org/wiki/Median) (**x̅** vs. **Med**), which are statistical estimates of a [typical value](https://www.itl.nist.gov/div898/handbook/eda/section3/eda351.htm). The [the spread, or variability](http://www.itl.nist.gov/div898/handbook/eda/section3/eda356.htm) of the sample is characterized by [standard deviation](https://en.wikipedia.org/wiki/Standard_deviation) (**s**) and [interquartile range](https://en.wikipedia.org/wiki/Interquartile_range) (**IQR**). They are followed in the series table by relative measures of this dispersion: the [coefficient of variation](https://en.m.wikipedia.org/wiki/Coefficient_of_variation) (**CV** = s / Mean); the equivalent for IQR is computed here as IQR / Median. Take note of the differences between these values for series with low iteration counts.<sup>[1](chart.html?f=Calculator+iters.json)</sup>

<iframe src="chart.html?f=Calculator+iters.json&hide=navigation+zoom+plots+boxplot+vertical-histogram+outliers&ry=359.8+460.2" name="Calculator+iters" frameborder="0" width="100%" height="680"></iframe>

*The range shown on Y axis is about 25% of the minimum value, as can be seen in **R** and **%** columns of the **i4** series. You can explore the individual sample series by selecting it from the table. It will be highlighted in the chart, with filled region showing the mean value of the series.*

In general, as less iterations are averaged in each reported sample, the variability of sample population increases. For example, there is quite extreme maximum value of 22586 in the *i1* series. This is probably the reason for originally introducing the averaging over multiple iterations in `Benchmark_X` in the first place. At least that’s how I understand Andrew Trick’s [recollection here](https://github.com/apple/swift/pull/8793#issuecomment-297791517).

But the increase in variability comes from measurement errors caused by preemptive multitasking. When the operating system’s scheduler interrupts our process in the middle of timing a benchmark, the reported sample time also includes the time it took to switch context to another process, its execution and switching back. The frequency and magnitude of these errors varies depending on the overall system load and is outside of our direct control. The higher iteration counts are averaging over longer stretches of time, therefore including more of the accumulated error. The worst case being our status quo, where the reported 1 sample/second also includes all interrupts to the measured process during that time.

What happens to the average of the mean with higher system load? The value currently used to detect improvements and regressions in our benchmark is the minimum of these averaged values, so we’ll examine that too. These are the values measured with *10 Series* strategy:

| Calculator | a | b | c | d | e |
|-|-|-|-|-|-|
| **Mean of x̅** | [368](chart.html?f=Calculator+a10.json) | [374](chart.html?f=Calculator+b10.json) | [401](Calculator+c10.json) | [615](chart.html?f=Calculator+d10.json) | [891](chart.html?f=Calculator+e10.json) |
| **Min of x̅** | [368](chart.html?f=Calculator+a10.json&s=i1c) | [372](chart.html?f=Calculator+b10.json&s=i1d) | [385](Calculator+c10.json&s=i2c) | [576](chart.html?f=Calculator+d10.json&s=i2d) | [779](chart.html?f=Calculator+e10.json&s=i2d) |

Current measurement system with auto-scaling always **reports the time with cumulative error** of all the interrupts that have occurred during the ~1s of measurement. This is the **root cause of instability** in the reported benchmark improvements and regressions. There are no unstable benchmarks. Our **measurement process is fragile** — easily susceptible to the whims of varying system load. Currently we only attempt to counteract it with brute force, looking for the lowest average sample gathered in about 20 seconds. We are also looking for an outlier there: a minimum of the means, not a typical value! With having just 20 samples overall, we have little indication of their quality. Smoke benchmark with 3 samples has hardly any statistical evidence for the reported improvements and regressions.

Due to the systemic measurement error introduced from preemptive multitasking, which has very long tail and is therefore nowhere near normally distributed, the **mean and standard deviation are poor estimates of a [location](https://www.itl.nist.gov/div898/handbook/eda/section3/eda351.htm) and [spread](http://www.itl.nist.gov/div898/handbook/eda/section3/eda356.htm)** for raw benchmark measurements when the system is even under moderate load.  **Median** and **interquartile range** are a more robust measures in the presence of outliers.

I think it is safe to conclude that averaging multiple samples together, i.e. measuring with `num-iters` > 1, serves no useful purpose and only precludes the separation of signal from the noise.

### Exclude Outliers
With the increased sampling frequency, it is possible to detect outliers and deal with them. Let’s examine the `i4` series from Calculator benchmark above in more detail.

On the left side of the scatter plot of individual samples is a [**box plot**](http://www.itl.nist.gov/div898/handbook/eda/section3/boxplot.htm), which shows the first [quartile](https://en.wikipedia.org/wiki/Quartile) (**Q1**, the 25th percentile), median (**Med**) and third quartile (**Q3**, 75th percentile) as filled rectangle. This box represents the middle 50% or the “body” of the data. Their difference is the **interquartile range** (**IQR** = Q3 - Q1). The whiskers protruding from it represent the minimum and maximum values.

There is a useful variation of the box plot that first computes *fence points*, which are used to detect the outliers. In our case, we are only concerned with outliers that increase our error, so we will keep the minimum and only use the **top inner fence** (**TIF** = Q3 + 1.5 * IQR), if it exceeds the maximum. All samples above this value will be considered **outliers**. 

This box plot variant also shows the mean values as a small horizontal lines, if it lies within the “clean” range (<= TIF) or as a circle if it lies above it. The [**scatter plot**](http://www.itl.nist.gov/div898/handbook/eda/section3/scatterp.htm) in the middle contains vertical lines denoting the median (solid line), Q1 and Q3 (dotted), mean (dashed) and TIF (dash-dot). On the right side of the scatter plot is the vertical [**histogram**](http://www.itl.nist.gov/div898/handbook/eda/section3/histogra.htm) (bin size is 1μs in this particular case).<sup>[2](chart.html?f=Calculator+iters.json&ry=364.8+390.2&s=i4)</sup>

<iframe src="chart.html?f=Calculator+iters.json&hide=navigation+zoom+stats+lagplot+histogram+outliers&ry=364.8+390.2&s=i4" frameborder="0" width="100%" height="640" name="Calculator+iters+i4"></iframe>

The *Runtimes* chart gives us another perspective by plotting the sampled values in ascending order. After working with the benchmark dataset for a while, it helps you get a feel for the probability distribution of the series. It is therefore also plotted as a micro chart in the first column of the series table.

From the runtimes chart we see that the top inner fence is computed at 370, which means that 90% of our samples are under this value and there are 53 outliers. To improve the quality and reliability of our measurement process we can borrow the box plot’s technique to exclude outlier samples from our dataset:<sup>[3](chart.html?f=Calculator+iters.json&ry=364.8+390.2&s=i4&outliers=clean)</sup>

<iframe src="chart.html?f=Calculator+iters.json&hide=navigation+zoom+stats+plots&ry=364.8+390.2&s=i4&outliers=clean" name="Calculator+iters+i4+clean" frameborder="0" width="100%" height="430"></iframe>

For benchmarks with low runtimes, which translates to plenty of samples during the 1s measurement, the high sampling frequency yields clear separation between the signal and noise. This is the same Calculator benchmark, this time from *d* series, i.e. measured on a 2 core machine with 3 processes — a very high load and a contested CPU scenario. Notice how the low Q1, Q3, IQR and Median values are stable across all series in contrast to the high and fluctuating Max, Range (R), Mean and  CV.<sup>[4](chart.html?f=Calculator+d10.json&s=i2d)</sup>

<iframe src="chart.html?f=Calculator+d10.json&hide=navigation+zoom+lagplot+histogram&s=i2d" name="Calculator+d10+i2d+raw" frameborder="0" width="100%" height="640"></iframe>

In the limit case, when the `Q1=Q3`, this technique can exclude at most 25% samples from the raw series, as can be seen in the case of *i2d* series selected in the runtimes chart above. Excluding outliers in the ideal case yields pure signal:<sup>[5](chart.html?f=Calculator+d10.json&s=i2d&outliers=clean)</sup>

<iframe src="chart.html?f=Calculator+d10.json&hide=navigation+zoom+plots+chart&s=i2d&outliers=clean" name="Calculator+d10+i2d+clean" frameborder="0" width="100%" height="270"></iframe>

Single one-second measurement, even when it collects thousands of individual samples, does not fully represent the measured benchmark in every case. Depending on the particular benchmark, there are various effects (caching, state of branch prediction) that can produce different typical values between a series of measurements. Therefore it is still important to conduct multiple independent runs of the benchmark. Aggregating samples from all series improves the robustness of measurement process, forming a more complete picture of the underlying probability distribution. When excluding outliers, the *all* series is the aggregate of individually cleaned series. An example of this is the [`EqualSubstringSubstring`](https://github.com/apple/swift/blob/master/benchmark/single-source/Substring.swift) benchmark from *a10R* series.<sup>[6](chart.html?f=EqualSubstringSubstring+a10R.json&outliers=clean)</sup>

<iframe src="chart.html?f=EqualSubstringSubstring+a10R.json&hide=navigation+zoom+stats&outliers=clean" name="EqualSubstringSubstring+a10R+clean" frameborder="0" width="100%" height="700"></iframe>

*There are two additional charts at the bottom: a histogram with bins sized to standard deviation and a [**lag plot**](https://www.itl.nist.gov/div898/handbook/eda/section3/lagplot.htm) that checks whether a data set or time series is random or not. This completes the demonstration of [exploratory data analysis techniques](https://www.itl.nist.gov/div898/handbook/eda/section3/eda33.htm) implemented in the `chart.html`. If you follow the numbered links, they open a standalone chart, which also includes navigation between the various series and benchmarks as well as zoom tools that were hidden in the embedded context of this document. I encourage you to explore the benchmark dataset in this browser based viewer, which is fully responsive, so that you can use it also on tablets and mobile phones. The state of the viewer is fully encoded in the URL, so if you find something interesting you want to discuss, just share the full URL.*

### Exclude Setup Overhead
Some benchmarks need to perform additional setup work before their main workload. Historically, this was dealt with by sizing the main workload so that it dwarfs the setup, making it negligible. Setup is performed before the main work loop, and its impact is further lessened by amortizing it over the `N` measured iterations.
<!--
Since we no longer measure with `N>1`, the effect of setup becomes more pronounced. One of the most extreme cases, benchmark [`ReversedArray`](https://github.com/apple/swift/blob/master/benchmark/single-source/ReversedCollections.swift) clearly demonstrates the amortization of the setup overhead as `num-iters` increase.<sup>[7](chart.html?f=ReversedArray+iters.json&ry=188.6+376.6&rx=0+1087235)</sup>

<iframe src="chart.html?b=ReversedArray&v=iters&hide=navigation+zoom+outliers+plots+stats+overhead+note&ry=188.6+376.6&rx=0+1087235" name="ReversedArray+iters+raw" frameborder="0" width="100%" height="430"></iframe>

The setup overhead is a systematic measurement error, that can be detected and corrected for, when measuring with different `num-iters`. Given two measurements performed with `i` and `j` iterations, that reported corresponding runtimes `ti` and `tj`, the setup overhead can be computed as follows: 

```setup = (i * j * (ti - tj)) / (j - i)```

We can detect the setup overhead by picking smallest minimum from series with same `num-iters` and using the above formula where `i=1, j=2`. In the *a10R* series from `ReversedArray` it gives us 134µs of setup overhead (or 41.4% of the minimal value).<sup>[7](chart.html?f=ReversedArray+iters.json&ry=188.6+376.6)</sup>

<iframe src="chart.html?b=ReversedArray&v=a10R&hide=navigation+zoom+outliers+plots+stats+note&ry=188.6+376.6" name="ReversedArray+a10R+raw" frameborder="0" width="100%" height="430"></iframe> 

We can normalize the series with different `num-iters` by subtracting the corresponding fraction of the setup from each sample. The median value after we exclude the setup overhead is 190µs which exactly matches the baseline from the [i0 Series](chart.html?f=ReversedArray+i0.json).<sup>[8](chart.html?f=ReversedArray+iters.json&ry=188.6+376.6&overhead=true)</sup>

<iframe src="chart.html?b=ReversedArray&v=a10R&hide=navigation+zoom+outliers+plots+stats+note&ry=188.6+376.6&overhead=true" name="ReversedArray+a10R+corrected" frameborder="0" width="100%" height="430"></iframe> 


Following test have setup overhead (with %):
TK

[PR 12404](https://github.com/apple/swift/pull/12404/commits) has added the ability to perform setup and tear down outside of the measured performance test that is so far used by one benchmark.
-->
### Memory Use
Collecting the maximum resident set size from the `time` command gives us a rough estimate of memory used by a benchmark during the measurement. The measured value is in bytes, but with a granularity of a single page (4 KB). When running `Benchmark_O` with nonexistent test 50 times, we establish a minimal baseline value of 2434 pages (9.5 MB) that jumps around between measurements. I guess this is due to varying amount of memory fragmentation the allocator deals with. The range is 13 pages (52KB), i.e. the maximum value seen was 2447 pages (9.56 MB). That is without taking any actual measurements, just instantiating the benchmarking process and processing command line parameters.

The `TypeFlood` benchmark which basically reduces to NOP in the optimized build adds at least additional 113 pages (0.44 MB). That seems to be the memory overhead introduced by the measurement infrastructure in the parent process that gets reported together.

Rebasing the `MAX_RSS` values measured for our series of benchmarks on the 2547 pages baseline (10 188 KB): 2/3 of benchmarks use less than 25 pages (100 KB). Of the remaining, some 70 benchmarks stay under 200 KB, about 50 tests are in 50-100 pages range (under 400 KB), remaining 52 go above that.

With the exception of 7 benchmarks, all benchmarks have constant memory use independent of the number of measured iterations. I suppose the following benchmarks are written incorrectly, because they vary the memory footprint of the base workload depending on the `N`: `Join`, `MonteCarloE`, `ArraySubscript` and 4 members of the `Observer*` family.

The `Array2D` benchmark has significant memory use range of 7MB (3292 — 5101 pages or 12.9 MB — 19.9 MB)! It creates a 1K by 1K `[[Int]]`, without reserving a capacity. The  pure `Int` storage is at least 8 MB, plus there is some constant overhead per Array. I guess the variation depends on how big contiguous memory regions the allocator gets, while the arrays are growing when `append` is called and they sometimes need to be copied to new region. Though I’m not sure this is the point of the test and it maybe should be rewritten with reserved capacity for stable memory use.

# Corrective Measures
Based on the above analysis I suggest we take following corrective measures:

* Ensure individual benchmarks conform to expected requirements by automating their validation (using `BenchmarkDoctor`):
  * Runtime under 2500 μs (with exceptions for individual members of benchmark families)
  * Negligible setup overhead (under 5% of runtime)
  * Constant memory use independent of iteration count
  * Benchmark name is less than or equal to 40 characters, to prevent obscuring results in report tables
* Measure memory use and context switches in Swift by calling `rusage` before 1st and after last sample is taken (abstracted for platform specific implementations)
* Exclude outliers from measured dataset by filtering run times that exceed (Q3 + 1.5 * IQR) (`--exclude-outliers=true` by default)
* Report following statistics for a performance test run:
  * Minimum, Q1, Median, Q3, Maximum, Mean, SD, n (number of samples after excluding outliers), number of context switches during measurement, TK ? Cumulative time (for whole measurement)
* Implement parallel benchmarking in `BenchmarkDriver` script to dramatically speed up measurement of the whole benchmark suite.

Other possible improvements:  
* Option to report 20 percentiles in 5% increments (because 10% don’t fall on Q1 and Q3 exactly); compressed in delta format where each successive value is expressed as delta from the previous data point.

# XXX
Current method to reduce variation in the samples is to average a 1s worth of them into the reported result. This achieves reduction of variation at the cost of inflating the true value by a random sampling of -naturally-(not true) distributed error.

TK We also need to significantly lower the workload inside the main loop of most tests, to allow the benchmark driver to call it with high enough frequency in-between time sampling. 
TK The workload inside the main loop should take comparable time to the time quantum assigned by the OS process scheduler to the processes when performing preemptive multitasking. 
TK The point is to be clearly able to distinguish between clean samples and samples that were interrupted by a different process. Empirically, when we can take at least 512 samples per second, the sample distribution is heavily skewed towards the minimum, making it easy to determine the mode.

