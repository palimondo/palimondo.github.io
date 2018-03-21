Previous: [Exclude Outliers](exclude-outliers.md)
### Exclude Setup Overhead
Some benchmarks need to perform additional setup work before their main workload. Historically, this was dealt with by sizing the main workload so that it dwarfs the setup, making it negligible. Setup is performed before the main work loop, and its impact is further lessened by amortizing it over the `N` measured iterations.

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

Next: [Memory Use](memory-use.md)<br/>