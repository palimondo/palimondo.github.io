## Corrective Measures
Given the fact Swift Benchmark Suite is a set of **microbenchmarks**, we are measuring effects that are manifested in **microseconds**. We can significantly increase the robustness of our measurement process by using proper statistical methods. Necessary prerequisite is having a representative sample population of reasonable size. From the experiment analyzed in previous sections it is apparent that we can make the measurement process resilient to the effects of varying system load if the benchmarked workload stays in range of hundreds of milliseconds, up to few thousand. Above that it becomes impossible to separate the signal from noise on a heavily contested CPU.

By making the runtime small, it takes less time to gather enough samples and their quality is better. By staying well under the 10 millisecond time slice we get more pristine samples and the samples that were interrupted by context switching are easier to identify. Excluding outliers makes our measurement more robust.

After these resilience preconditions are met, we can speed up the whole measurement process by running it in parallel on all available CPU cores. If we gather 10 independent one-second measurements on a 10 core machine, we can run the whole Benchmark Suite in 500 seconds, while having much better confidence in the statistical significance of the reported results!

Based on the preceding analysis I suggest we take the following corrective measures:
### One-time Benchmark Suite Cleanup
* Enable increase of measurement frequency by **lowering the base workload** of individual benchmarks to run **under 2500 μs**. For vast majority of benchmarks this just means lowering the constant used to drive their inner loop — effectively allowing the measurement infrastructure to peek inside the work loop more often. Benchmarks that are part of test family meant to highlight the relative costs should be exempt from strictly meeting this requirement. See for example the [`DropFirst`](https://github.com/apple/swift/blob/master/benchmark/single-source/DropFirst.swift) family of benchmarks.
* Ensure the **setup overhead is under 5%**. Expensive setup work (> 5%) is excluded from main measurement by using the setup and teardown methods. Also reassess the ratio of setup to the main workload, so that it stays reasonable (<20%) and doesn’t needlessly prolong the measurement.
* Ensure benchmarks have **constant memory use** independent of iteration count.
* Make all **benchmark names <= 40 characters** long to prevent obscuring results in report tables.
* Make all benchmark **names use CamelCase** convention.

### Measurement System Improvements
* **Measure memory use and context switches in Swift** by calling `rusage` before 1st and after last sample is taken (abstracted for platform specific implementations). This change is meant to exclude the overhead introduced by the measurement infrastructure, which is impossible to correct for from external scripts.
* **Exclude outliers** from the measured dataset by filtering samples whose runtime exceed top inner fence (**TIF** = Q3 + 1.5 * IQR), controlled by newly added `--exclude-outliers` option that will default to `true`.
* **Expand the statistics reported** for each a benchmark run:
  ** Minimum, **Q1**, Median, **Q3**, Maximum (to complete the [5 number summary](https://en.wikipedia.org/wiki/Five-number_summary)), Mean, SD, n (number of samples after excluding outliers), **maximum resident set size** (in pages?), number of involuntary context switches (**ICS**) during measurement.
  ** Option to report 20 percentiles in 5% increments (or 20 number summary; because 10% don’t fall on Q1 and Q3 exactly) compressed in delta format where each successive value is expressed as delta from the previous percentile.
* Implement **parallel benchmarking** in `BenchmarkDriver` script to dramatically speed up measurement of the whole benchmark suite.
* Introduce **automated benchmark validation** to ensure individual benchmarks conform to the expected requirements, which will be performed for newly added tests during regular CI benchmarks and on the whole benchmark suite as a part of the validation tests. See [`BenchmarkDoctor`](https://bit.ly/VK-BD#L163) for a prototype implementation.
TK how to detect regressions and improvements?
TK Further improvements: detecting modes

Previous: [Memory Use](memory-use.md)