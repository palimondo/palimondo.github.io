## Detecting Changes
When we look at benchmarks from our dataset, where we have enough samples (runtimes under 1000μs), it becomes clear that part of our challenge is detecting performance changes based on samples that have various distribution characteristics. Lot of the benchmarks have **multimodal distribution** and it’s apparent that the **system load** (as measured by the **ICS** proxy) **is the factor** that effects sample variance as well as the relative distribution of values between the modes. This means we are probably entering the realm of multivariate statistics… and my hair is on fire 😱🔥!

But the question of what constitutes a significant change in performance of a benchmark remains. As argued in previous chapters, using the **mean** value and **standard deviation** is problematic, because the benchmark dataset is not normally distributed and mean is biased by the accumulated error. Should we be using more robust location and scale measures like **median** and **IQR**? How about not changing our method and continuing to use the **minimum**?

### Status Quo
The way we detect if benchmarks have improved or regressed is implemented in [`compare_perf_tests.py`](https://github.com/apple/swift/blob/master/benchmark/scripts/compare_perf_tests.py). It takes the minimum runtime for each benchmark measured from the two compared branches and if their difference is more than `delta_threshold` parameter (defaults to 0.05 or 5%), they are reported as an improvement or a regression. This is fragile for tests with low absolute runtimes (tens of microseconds), as they [easily jump over the 5%](https://github.com/apple/swift/pull/9806#issuecomment-303370149) improvement/regression threshold on small changes to reported runtime. *Note that this “change detection” is not based on any statistical test of significance. It doesn’t even consider the variance of sample population. It’s more like a wet finger in the wind…*

If the ranges (min, max) for changed benchmarks overlap, they are flagged with a `?` in the report. Given that range is very sensitive to outliers, almost all changes are marked this way, significantly diminishing the utility of this feature.

### Issues with Minimum as Location Estimator
On the swift-dev mailing list [Michael Gottesmann explained](https://forums.swift.org/t/measuring-mean-performance-was-questions-about-swift-ci/6106/3?u=palimondo):
> The reason why we use the ***min*** is that statistically we are not interested in estimating the ***mean*** or ***center*** of the distribution. Rather, we are actually interested in the ***”speed of light”*** of the computation implying that we are looking for the min.

This matches the justification for use of the minimum estimator given in [Chen, J., & Revels, J. (2016). Robust benchmarking in noisy environments.](https://arxiv.org/pdf/1608.04295.pdf):
> Thus for our purposes, the *minimum* is a unimodal, robust estimate for the location parameter of a given benchmark’s timing distribution.

In the paper’s context, *the purpose* was similar to our use of *minimum* runtime from 3 samples to estimate the [number of samples required for ~1s measurement](index.md#increased-measurement-frequency-and-scaling-with-brackets). 

That paper also mentions the issue of multimodal distributions in the benchmarking dataset and thoroughly describes the source of measurement errors, but is mainly concerned with determining the ideal number of iterations to take for a sample on the nanosecond scale:
> Our procedure estimates a value for *n* which primarily minimizes error in timing measurements and secondarily maximizes the number of measurements obtainable within a given time budget.

But in the conclusion the paper’s authors expand the claim:
> Our results suggest that using the minimum estimator for the true run time of a benchmark, rather than the mean or median, is robust to non-ideal statistics and also provides the smallest error.

Looking at the overall stability of Min, Q1, Med, Q3 and Max across the whole Swift Benchmark Suite (after [excluding outliers](exclude-outliers.md) as described before), it is indeed true that the minimum is the most stable estimator under varying system load. Next best is Q1, followed by Median, etc. But all that is just the logical consequence of rising variance due to the rising system load. So the use of minimum as robust location estimator makes some sense.

But there are few benchmarks with the minimum values that are very rare and significant outliers, which probably means they are incorrectly written (looks like there is some kind of bug in the bridging implementation). Following table summarizes the strange outliers in relation to the mode.

| Benchmark | Minimum | Mode | Maximum |
|--|--|--|--|
| [ObjectiveCBridgeStubFromNSDate](chart.html?b=ObjectiveCBridgeStubFromNSDate&v=a10&ry=3888+92049) | | ~8.9k | ~**85k** |
| [ObjectiveCBridgeStubFromNSDateRef](chart.html?b=ObjectiveCBridgeStubFromNSDateRef&v=a10&ry=4557+92008) | | ~9.5k | ~**85k** |
| [ObjectiveCBridgeStubToNSDateRef](chart.html?b=ObjectiveCBridgeStubToNSDateRef&v=b10R&ry=4556+22481) | ~**4.6k** | ~9.5k | ~**85k** |
| [ObjectiveCBridgeStubToNSDate](chart.html?b=ObjectiveCBridgeStubToNSDate&v=b10R&ry=9893+121418) | ~**10k** | ~43k | ~**120k** |
| [ObjectiveCBridgeStubNSDateMutationRef](chart.html?b=ObjectiveCBridgeStubNSDateMutationRef&v=b10R&ry=9340+106303) | ~**10k** | ~56k | |

Minimum occurs in just 1%-5% of samples in a series and the outlier maximum is *always the first* measurement.

The [`CharacterLiteralsSmall`](https://github.com/apple/swift/blob/master/benchmark/single-source/CharacterLiteralsSmall.swift) is an example of benchmark with multimodal distribution with 3 very distinct modes at 873, 898 and 920μs. Sometimes, under higher system load, like in the case of *e10R Series*, a fourth smaller and normally distributed peak appears around 910μs.<sup>[9](chart.html?b=CharacterLiteralsSmall&v=c10)</sup>

<iframe src="chart.html?b=CharacterLiteralsSmall&v=c10&outliers=clean&hide=zoom+navigation+histogram&ry=819+981" frameborder="0" width="100%" height="640"></iframe>

The main body of data between the two outside modes is 47μs (5%) wide, but sporadically a very rare outlier minimum appears with value of 823, additional 50μs below the Q1. That makes this benchmark potentially unstable because such value appears literally 1-5 times in 7000 samples. In this case, the minimum doesn’t appear to be a robust estimator.

Remaining issue is the method to determine if we have a significant change. Michael Gottesmann suggested we should use the Mann-Whitney U-test. It is also used for the same purpose in [lnt](http://llvm.org/docs/lnt/). I agree that if we use the minimums from 10 independent runs per benchmark as their location estimate, it might work better than what we do now. But by using just a few of these extreme samples, I don’t think we can make many claims about statistical significance of detected changes or present some confidence intervals etc…

### Future Directions
Browsing through the benchmark data set, comparing the vertical histograms for different loads for a given benchmark, it looks like there always forms quite a distinct mode (or more than one) around the lower part of distribution. It seem very robust to the system load variation. I’d like to further investigate use of **mode** as estimator for benchmark runtime more robust than minimum. [Knuth, K.H., (2013) Optimal Data-Based Binning for Histograms](https://arxiv.org/pdf/physics/0605197.pdf) look very promising, given its Python [implementation in AstroML](https://github.com/astroML/astroML/blob/master/astroML/density_estimation/histtools.py) is readily available.

Previous: [Exclude Setup Overhead](exclude-setup-overhead.md)<br/>
Next: [Memory Use](memory-use.md)