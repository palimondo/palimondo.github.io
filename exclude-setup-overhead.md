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

However, our ability to detect overhead with this technique depends on its size relative to the sample variance. For this reason, small overheads get hidden under noisier machine. Some overhead becomes apparent only in the *a* Series and gets lost in noisier series. Another issue is that for larger overheads, when we subtract it, the corrected sample has higher the variance relative to other benchmarks with similar runtimes. This is because the sample dispersion is always relative to the runtime. When we subtract the constant overhead we get better runtime, but same dispersion (i.e. the IQR and standard deviation are unchanged).

Benchmarks from Swift Benchmark Suite with setup overhead in % relative to the runtime. 
*The % links open the `chart.html`; Hover over the links for absolute values in µs*:

| Benchmark | a10 | a10R | a12 |
|---|---|---|---|
| ClassArrayGetter | [100%](chart.html?f=ClassArrayGetter+a10.json "5974µs") | [100%](chart.html?f=ClassArrayGetter+a10R.json "6000µs") | [99%](chart.html?f=ClassArrayGetter+a12.json "5950µs") |
| ReversedDictionary | [99%](chart.html?f=ReversedDictionary+a10.json "48700µs") | [99%](chart.html?f=ReversedDictionary+a10R.json "48750µs") | [100%](chart.html?f=ReversedDictionary+a12.json "48896µs") |
| ArrayOfGenericRef | [49%](chart.html?f=ArrayOfGenericRef+a10.json "16292µs") | [50%](chart.html?f=ArrayOfGenericRef+a10R.json "16538µs") | [50%](chart.html?f=ArrayOfGenericRef+a12.json "16664µs") |
| ArrayOfPOD | [50%](chart.html?f=ArrayOfPOD+a10.json "622µs") | [50%](chart.html?f=ArrayOfPOD+a10R.json "622µs") | [50%](chart.html?f=ArrayOfPOD+a12.json "622µs") |
| ArrayOfGenericPOD | [50%](chart.html?f=ArrayOfGenericPOD+a10.json "662µs") | [50%](chart.html?f=ArrayOfGenericPOD+a10R.json "664µs") | [50%](chart.html?f=ArrayOfGenericPOD+a12.json "664µs") |
| Chars | [50%](chart.html?f=Chars+a10.json "3194µs") | [50%](chart.html?f=Chars+a10R.json "3190µs") | [50%](chart.html?f=Chars+a12.json "3194µs") |
| ArrayOfRef | [49%](chart.html?f=ArrayOfRef+a10.json "16018µs") | [50%](chart.html?f=ArrayOfRef+a10R.json "16126µs") | [49%](chart.html?f=ArrayOfRef+a12.json "16000µs") |
| ReversedArray | [41%](chart.html?f=ReversedArray+a10.json "134µs") | [41%](chart.html?f=ReversedArray+a10R.json "134µs") | [41%](chart.html?f=ReversedArray+a12.json "134µs") |
| DictionaryGroupOfObjects | [36%](chart.html?f=DictionaryGroupOfObjects+a10.json "5872µs") | [34%](chart.html?f=DictionaryGroupOfObjects+a10R.json "5614µs") | [36%](chart.html?f=DictionaryGroupOfObjects+a12.json "5934µs") |
| ArrayAppendStrings | [24%](chart.html?f=ArrayAppendStrings+a10.json "23408µs") | [26%](chart.html?f=ArrayAppendStrings+a10R.json "24826µs") | [25%](chart.html?f=ArrayAppendStrings+a12.json "24228µs") |
| SetIsSubsetOf_OfObjects | [20%](chart.html?f=SetIsSubsetOf_OfObjects+a10.json "462µs") | [20%](chart.html?f=SetIsSubsetOf_OfObjects+a10R.json "460µs") | [20%](chart.html?f=SetIsSubsetOf_OfObjects+a12.json "460µs") |
| SortSortedStrings | [15%](chart.html?f=SortSortedStrings+a10.json "436µs") | [15%](chart.html?f=SortSortedStrings+a10R.json "440µs") | [15%](chart.html?f=SortSortedStrings+a12.json "440µs") |
| IterateData | [10%](chart.html?f=IterateData+a10.json "518µs") | [13%](chart.html?f=IterateData+a10R.json "690µs") | [11%](chart.html?f=IterateData+a12.json "576µs") |
| SuffixArray | [10%](chart.html?f=SuffixArray+a10.json "6µs") | [7%](chart.html?f=SuffixArray+a10R.json "4µs") | [10%](chart.html?f=SuffixArray+a12.json "6µs") |
| PolymorphicCalls | [10%](chart.html?f=PolymorphicCalls+a10.json "6µs") | [10%](chart.html?f=PolymorphicCalls+a10R.json "6µs") | [10%](chart.html?f=PolymorphicCalls+a12.json "6µs") |
| Phonebook | [9%](chart.html?f=Phonebook+a10.json "1498µs") | [9%](chart.html?f=Phonebook+a10R.json "1588µs") | [9%](chart.html?f=Phonebook+a12.json "1556µs") |
| SetIntersect_OfObjects | [8%](chart.html?f=SetIntersect_OfObjects+a10.json "860µs") | [8%](chart.html?f=SetIntersect_OfObjects+a10R.json "890µs") | [9%](chart.html?f=SetIntersect_OfObjects+a12.json "950µs") |
| SetIsSubsetOf | [9%](chart.html?f=SetIsSubsetOf+a10.json "136µs") | [9%](chart.html?f=SetIsSubsetOf+a10R.json "134µs") | [9%](chart.html?f=SetIsSubsetOf+a12.json "136µs") |
| DropLastArray | [9%](chart.html?f=DropLastArray+a10.json "4µs") | [9%](chart.html?f=DropLastArray+a10R.json "4µs") | [9%](chart.html?f=DropLastArray+a12.json "4µs") |
| Dictionary | [7%](chart.html?f=Dictionary+a10.json "204µs") | [8%](chart.html?f=Dictionary+a10R.json "220µs") | [8%](chart.html?f=Dictionary+a12.json "234µs") |
| SetIntersect | [8%](chart.html?f=SetIntersect+a10.json "272µs") | [8%](chart.html?f=SetIntersect+a10R.json "268µs") | [8%](chart.html?f=SetIntersect+a12.json "272µs") |
| DictionaryOfObjects | [8%](chart.html?f=DictionaryOfObjects+a10.json "832µs") | [7%](chart.html?f=DictionaryOfObjects+a10R.json "780µs") | [7%](chart.html?f=DictionaryOfObjects+a12.json "746µs") |
| MapReduceShort | [7%](chart.html?f=MapReduceShort+a10.json "812µs") | [6%](chart.html?f=MapReduceShort+a10R.json "642µs") | [5%](chart.html?f=MapReduceShort+a12.json "528µs") |
| DropLastArrayLazy | [7%](chart.html?f=DropLastArrayLazy+a10.json "4µs") | [7%](chart.html?f=DropLastArrayLazy+a10R.json "4µs") | [7%](chart.html?f=DropLastArrayLazy+a12.json "4µs") |
| StaticArray | [7%](chart.html?f=StaticArray+a10.json "2µs") | [7%](chart.html?f=StaticArray+a10R.json "2µs") | [7%](chart.html?f=StaticArray+a12.json "2µs") |
| SuffixArrayLazy | [6%](chart.html?f=SuffixArrayLazy+a10.json "4µs") | [6%](chart.html?f=SuffixArrayLazy+a10R.json "4µs") | [6%](chart.html?f=SuffixArrayLazy+a12.json "4µs") |
| MapReduceClass | [6%](chart.html?f=MapReduceClass+a10.json "716µs") | [4%](chart.html?f=MapReduceClass+a10R.json "498µs") | [4%](chart.html?f=MapReduceClass+a12.json "482µs") |
| ArrayInClass | [4%](chart.html?f=ArrayInClass+a10.json "134µs") | [5%](chart.html?f=ArrayInClass+a10R.json "154µs") | [5%](chart.html?f=ArrayInClass+a12.json "144µs") |
| SubstringFromLongString | [4%](chart.html?f=SubstringFromLongString+a10.json "2µs") | [4%](chart.html?f=SubstringFromLongString+a10R.json "2µs") | [4%](chart.html?f=SubstringFromLongString+a12.json "2µs") |
| DropFirstArray | [4%](chart.html?f=DropFirstArray+a10.json "6µs") | [4%](chart.html?f=DropFirstArray+a10R.json "6µs") | [4%](chart.html?f=DropFirstArray+a12.json "6µs") |
| PrefixArray | [3%](chart.html?f=PrefixArray+a10.json "4µs") | [3%](chart.html?f=PrefixArray+a10R.json "4µs") | [3%](chart.html?f=PrefixArray+a12.json "4µs") |
| SuffixAnyCollection | [3%](chart.html?f=SuffixAnyCollection+a10.json "2µs") | [3%](chart.html?f=SuffixAnyCollection+a10R.json "2µs") | [3%](chart.html?f=SuffixAnyCollection+a12.json "2µs") |
| DropLastAnyCollection | [3%](chart.html?f=DropLastAnyCollection+a10.json "2µs") | [3%](chart.html?f=DropLastAnyCollection+a10R.json "2µs") | [3%](chart.html?f=DropLastAnyCollection+a12.json "2µs") |
| SetUnion_OfObjects | [3%](chart.html?f=SetUnion_OfObjects+a10.json "1002µs") | [2%](chart.html?f=SetUnion_OfObjects+a10R.json "652µs") | [3%](chart.html?f=SetUnion_OfObjects+a12.json "1032µs") |
| PrefixArrayLazy | [3%](chart.html?f=PrefixArrayLazy+a10.json "4µs") | [3%](chart.html?f=PrefixArrayLazy+a10R.json "4µs") | [3%](chart.html?f=PrefixArrayLazy+a12.json "4µs") |
| UTF8Decode | [2%](chart.html?f=UTF8Decode+a10.json "36µs") | [2%](chart.html?f=UTF8Decode+a10R.json "48µs") | [2%](chart.html?f=UTF8Decode+a12.json "40µs") |
| PrefixWhileArrayLazy | [2%](chart.html?f=PrefixWhileArrayLazy+a10.json "4µs") | [2%](chart.html?f=PrefixWhileArrayLazy+a10R.json "4µs") | [2%](chart.html?f=PrefixWhileArrayLazy+a12.json "4µs") |
| DropFirstArrayLazy | [2%](chart.html?f=DropFirstArrayLazy+a10.json "4µs") | [2%](chart.html?f=DropFirstArrayLazy+a10R.json "4µs") | [2%](chart.html?f=DropFirstArrayLazy+a12.json "4µs") |
| SetExclusiveOr_OfObjects | [2%](chart.html?f=SetExclusiveOr_OfObjects+a10.json "742µs") | [2%](chart.html?f=SetExclusiveOr_OfObjects+a10R.json "882µs") | [2%](chart.html?f=SetExclusiveOr_OfObjects+a12.json "854µs") |
| DropFirstSequenceLazy | [2%](chart.html?f=DropFirstSequenceLazy+a10.json "180µs") | [2%](chart.html?f=DropFirstSequenceLazy+a10R.json "178µs") | [2%](chart.html?f=DropFirstSequenceLazy+a12.json "190µs") |
| DropWhileArrayLazy | [1%](chart.html?f=DropWhileArrayLazy+a10.json "6µs") | [1%](chart.html?f=DropWhileArrayLazy+a10R.json "6µs") | [1%](chart.html?f=DropWhileArrayLazy+a12.json "6µs") |
| DropFirstAnyCollection | [1%](chart.html?f=DropFirstAnyCollection+a10.json "2µs") | [1%](chart.html?f=DropFirstAnyCollection+a10R.json "2µs") | [1%](chart.html?f=DropFirstAnyCollection+a12.json "2µs") |
| PrefixAnyCollection | [1%](chart.html?f=PrefixAnyCollection+a10.json "2µs") | [1%](chart.html?f=PrefixAnyCollection+a10R.json "2µs") | [1%](chart.html?f=PrefixAnyCollection+a12.json "2µs") |
| MapReduceLazySequence | [1%](chart.html?f=MapReduceLazySequence+a10.json "2µs") | [1%](chart.html?f=MapReduceLazySequence+a10R.json "2µs") | [1%](chart.html?f=MapReduceLazySequence+a12.json "2µs") |
| ArrayAppendToFromGeneric | [1%](chart.html?f=ArrayAppendToFromGeneric+a10.json "16µs") | [1%](chart.html?f=ArrayAppendToFromGeneric+a10R.json "22µs") | [0%](chart.html?f=ArrayAppendToFromGeneric+a12.json "10µs") |
| PrefixWhileAnyCollectionLazy | [1%](chart.html?f=PrefixWhileAnyCollectionLazy+a10.json "2µs") | [1%](chart.html?f=PrefixWhileAnyCollectionLazy+a10R.json "2µs") | [1%](chart.html?f=PrefixWhileAnyCollectionLazy+a12.json "2µs") |

The first two, [`ClassArrayGetter`](https://github.com/apple/swift/blob/master/benchmark/single-source/ClassArrayGetter.swift) and [ReversedDictionary](https://github.com/apple/swift/blob/master/benchmark/single-source/ReversedCollections.swift) are clearly cases of incorrectly written benchmarks where the compiler’s optimizations eliminated the main workload and we are only measuring the setup overhead.

[PR 12404](https://github.com/apple/swift/pull/12404/commits) has added the ability to perform setup and tear down outside of the measured performance test that is so far used by one benchmark.

Rather than automatically correct for the setup overhead, I believe it is best to manually audit the benchmarks from the above table and reassess what should be measured and what should be moved to the setup function outside the main workload.

Next: [Memory Use](memory-use.md)<br/>