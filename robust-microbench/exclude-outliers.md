### Exclude Outliers
With the increased sampling frequency, it is possible to detect outliers and deal with them. Let’s examine the `i4` series from Calculator benchmark above in more detail.

On the left side of the scatter plot of individual samples is a [**box plot**](https://www.itl.nist.gov/div898/handbook/eda/section3/boxplot.htm), which shows the first [quartile](https://en.wikipedia.org/wiki/Quartile) (**Q1**, the 25th percentile), median (**Med**) and third quartile (**Q3**, 75th percentile) as filled rectangle. This box represents the middle 50% or the “body” of the data. Their difference is the **interquartile range** (**IQR** = Q3 - Q1). The whiskers protruding from it represent the minimum and maximum values.

There is a useful variation of the box plot that first computes *fence points*, which are used to detect the outliers. In our case, we are only concerned with outliers that increase our error, so we will keep the minimum and only use the **top inner fence** (**TIF** = Q3 + 1.5 * IQR), if it exceeds the maximum. All samples above this value will be considered **outliers**.

This box plot variant also shows the mean values as a small horizontal lines, if it lies within the “clean” range (<= TIF) or as a circle if it lies above it. The [**scatter plot**](https://www.itl.nist.gov/div898/handbook/eda/section3/scatterp.htm) in the middle contains vertical lines denoting the median (solid line), Q1 and Q3 (dotted), mean (dashed) and TIF (dash-dot). On the right side of the scatter plot is the vertical [**histogram**](https://www.itl.nist.gov/div898/handbook/eda/section3/histogra.htm) (bin size is 1μs in this particular case).<sup>[2](chart.html?b=Calculator&v=iters&ry=364.8+390.2&s=i4)</sup>

<iframe src="chart.html?b=Calculator&v=iters&hide=navigation+zoom+stats+lagplot+histogram+outliers&ry=364.8+390.2&s=i4" frameborder="0" width="100%" height="640" name="Calculator+iters+i4"></iframe>

The *Runtimes* chart gives us another perspective by plotting the sampled values in ascending order. After working with the benchmark dataset for a while, it helps you get a feel for the probability distribution of the series. It is therefore also plotted as a micro chart in the first column of the series table.

From the runtimes chart we see that the top inner fence is computed at 370μs, which means that 90% of our samples are under this value and there are 53 outliers. To improve the quality and reliability of our measurement process we can borrow the box plot’s technique to exclude outlier samples from our dataset:<sup>[3](chart.html?b=Calculator&v=iters&ry=364.8+390.2&s=i4&outliers=clean)</sup>

<iframe src="chart.html?b=Calculator&v=iters&hide=navigation+zoom+stats+plots&ry=364.8+390.2&s=i4&outliers=clean" name="Calculator+iters+i4+clean" frameborder="0" width="100%" height="430"></iframe>

For benchmarks with low runtimes, which translates to plenty of samples during the 1s measurement, the high sampling frequency yields clear separation between the signal and noise. This is the same Calculator benchmark, this time from *d* series, i.e. measured on a 2 core machine with 3 processes — a very high load and a contested CPU scenario. Notice how the low Q1, Q3, IQR and Median values are stable across all series in contrast to the high and fluctuating Max, Range (R), Mean and  CV.<sup>[4](chart.html?b=Calculator&v=d10&s=i2d)</sup>

<iframe src="chart.html?b=Calculator&v=d10&hide=navigation+zoom+lagplot+histogram&s=i2d" name="Calculator+d10+i2d+raw" frameborder="0" width="100%" height="640"></iframe>

In the limit case, when the `Q1=Q3`, this technique can exclude at most 25% samples from the raw series, as can be seen in the case of *i2d* series selected in the runtimes chart above. Excluding outliers in the ideal case yields pure signal:<sup>[5](chart.html?b=Calculator&v=d10&s=i2d&outliers=clean)</sup>

<iframe src="chart.html?b=Calculator&v=d10&hide=navigation+zoom+plots+chart&s=i2d&outliers=clean" name="Calculator+d10+i2d+clean" frameborder="0" width="100%" height="270"></iframe>

Single one-second measurement, even when it collects thousands of individual samples, does not fully represent the measured benchmark in every case. Depending on the particular benchmark, there are various effects (caching, state of branch prediction) that can produce different typical values between a series of measurements. Therefore it is still important to conduct multiple independent runs of the benchmark. Aggregating samples from all series improves the robustness of measurement process, forming a more complete picture of the underlying probability distribution. When excluding outliers, the *all* series is the aggregate of individually cleaned series. An example of this is the [`EqualSubstringSubstring`](https://github.com/apple/swift/blob/master/benchmark/single-source/Substring.swift) benchmark from *a10R* series.<sup>[6](chart.html?b=EqualSubstringSubstring&v=a10R&outliers=clean)</sup>

<iframe src="chart.html?b=EqualSubstringSubstring&v=a10R&hide=navigation+zoom+stats&outliers=clean" name="EqualSubstringSubstring+a10R+clean" frameborder="0" width="100%" height="700"></iframe>

*There are two additional charts at the bottom: a histogram with bins sized to standard deviation and a [**lag plot**](https://www.itl.nist.gov/div898/handbook/eda/section3/lagplot.htm) that checks whether a data set or time series is random or not. This completes the demonstration of [exploratory data analysis techniques](https://www.itl.nist.gov/div898/handbook/eda/section3/eda33.htm) implemented in the `chart.html`. If you follow the numbered links, they open a standalone chart, which also includes navigation between the various series and benchmarks as well as zoom tools that were hidden in the embedded context of this document. I encourage you to explore the benchmark dataset in this browser based viewer, which is fully responsive, so that you can use it also on tablets and mobile phones. The state of the viewer is fully encoded in the URL, so if you find something interesting you want to discuss, just share the full URL.*

Previous: [Analysis](analysis.md)<br/>
Next: [Exclude Setup Overhead](exclude-setup-overhead.md)