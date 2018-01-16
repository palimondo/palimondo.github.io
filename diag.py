import json
import subprocess
import gc

from math import log
from Benchmark_Driver import BenchmarkDriver
from compare_perf_tests import PerformanceTestSamples
from compare_perf_tests import Sample

class ArgsStub(object):
    def __init__(self):
        self.benchmarks = '1'
        self.filters = None
        self.tests = ('/Users/mondo/Developer/swift-source/build/'
                      'Ninja-ReleaseAssert/swift-macosx-x86_64/bin')
        self.optimization = 'O'
        self.measure_environment = False

args = ArgsStub()
driver = BenchmarkDriver(args)

def adjusted_1s_samples(runtime, i=1):
    if (runtime ==  0):
        return 0
    s = 1000000 / float(runtime * i) # samples for 1s run
    s = int(pow(2, round(log(s, 2))))  # rounding down to power of 2
    return s if s > 2 else 2

def run_args(s, i=1):
    while (s > 1):
        yield (s, i)
        i = i * 2
        s = s / 2

def vary_iterations(t, reverse=False, cap=None):
    ras = list(run_args(adjusted_1s_samples(run(t).min)))
    if cap:
        ras = ras[:cap]
    if reverse:
        ras = reversed(ras)
    for (s, i) in ras:
        print i
        res = run(t, s, i, True)
        driver.results[res.name + ' i' + str(i) + ('r' if reverse else '')] = res
        print res
        print res.samples

# TODO measure memory - could be interesting to see varying iterations/num_samples

def run(t, s=3, i=1, verbose=True):
    t = t if isinstance(t, str) else str(t)
    r = driver.run(t, s, i, verbose, measure_environment=True)
    gc.collect()
    driver.last_run = r
    if r.name not in driver.results:
        driver.results[r.name] = r
    else:
        driver.results[r.name].merge(r)
    return r

def num_iters(result):
    return result.samples.samples[0].num_iters

def series(result, name=None):
    return {
        'name' : name if name else '{0} i{1}'.format(result.name, num_iters(result)),
        'num_iters' : num_iters(result),
        'involuntary_cs' : result.involuntary_cs if hasattr(result, 'involuntary_cs') else None,
        'voluntary_cs' : result.voluntary_cs  if hasattr(result, 'voluntary_cs') else None,
        'max_rss' : result.max_rss  if hasattr(result, 'max_rss') else None,
        'data' : [sample.runtime for sample in result.samples.all_samples]}


def series_data(test):
    return {
        'name': test,
        'type': 'num_iters',
        'series': [series(test_result, test_run_name)
                   for test_run_name, test_result in driver.results.items()
                   if test_run_name.startswith(test + ' ')]}

def bidi_triplet(t, rev=False):
    if rev:
        vary_iterations(t, cap=3)
        iters(t, True, cap=3)
    else:
        vary_iterations(t, True, 3)
        iters(t, cap=3)

def octet(t):
    ras = list(run_args(adjusted_1s_samples(run(t).min)))[:3]
    ras = list(reversed(ras))
    for suffix in ['a', 'b', 'c']:
        for (s, i) in ras:
            res = run(t, s, i, True)
            driver.results[res.name + ' i' + str(i) + suffix] = res
            print res.samples
    save_samples(driver.last_run.name, driver.last_run.name + ' octet.json')
    # open_chart_in_safari()

def dozen(t):
    ras = list(run_args(adjusted_1s_samples(run(t).min)))[:3]
    ras = list(reversed(ras))
    for suffix in ['a', 'b', 'c', 'd']:
        for (s, i) in ras:
            res = run(t, s, i, True)
            driver.results[res.name + ' i' + str(i) + suffix] = res
            print res.samples
    save_samples(driver.last_run.name, driver.last_run.name + ' dozen.json')
    # open_chart_in_safari()

def ten(t):
    suffixes = list('abcdefghij')
    ras = list(run_args(adjusted_1s_samples(run(t).min)))[:2]
    num_series = [10] if len(ras) < 2 else [6, 4]
    def capped(samples): return min(samples, 4096)

    for (i, params) in zip(num_series, ras):
        for suffix in suffixes[:i]:
            num_samples, num_iters = params
            res = run(t, capped(num_samples), num_iters, True)
            driver.results[res.name + ' i' + str(num_iters) + suffix] = res
            print res.samples

    save_samples(driver.last_run.name, driver.last_run.name + ' d10.json')
    # open_chart_in_safari()

def long(t):
    ras = list(run_args(adjusted_1s_samples(run(t).min)))[:1]
    for suffix in ['a', 'b', 'c', 'd']:
        for (s, i) in ras:
            res = run(t, s * 20, i, True)
            driver.results[res.name + ' i' + str(i) + suffix] = res
            print res.samples
    save_samples(driver.last_run.name, driver.last_run.name + ' long.json')


def i0(t):
    run(t, s=1)  # don't need calibration, but need dummy result for merging samples
    for suffix in ['a', 'b', 'c', 'd']:
        res = run(t, 20, 0, True)
        driver.results[res.name + ' ' + suffix] = res
        print res.samples
    save_samples(driver.last_run.name, driver.last_run.name + ' i0.json')
    # open_chart_in_safari()

def sq(t):  # status quo
    run(t, s=1)  # don't need calibration, but need dummy result for merging samples
    for suffix in ['a', 'b', 'c', 'd']:
        for i in range(0,20):
            res = run(t, 1, 0, True)
            run_name = res.name + ' i0_' + suffix
            if run_name not in driver.results:
                driver.results[run_name] = res
            else:
                s = res.samples.samples[0]
                s = Sample(i, s.num_iters, s.runtime)
                driver.results[run_name].samples.add(s)
                driver.results[run_name].involuntary_cs += res.involuntary_cs
        driver.results[run_name].samples.exclude_outliers()
        print driver.results[run_name].samples
    save_samples(driver.last_run.name, driver.last_run.name + ' sq.json')
    # open_chart_in_safari()

def cal(s, e):
    for t in range(s,e):
        r = run(t)
        yield (t, adjusted_1s_samples(r.min))

# FIXME AttributeError: 'BenchmarkDriver' object has no attribute 'last_run'
# def save_samples(test=driver.last_run.name, file_name='f.json'):
def save_samples(test, file_name='f.json'):
    with open(file_name, 'w') as f:
        json.dump(series_data(test), f,
                  separators=(',',':'))  # compact seriaization
#    open_chart_in_safari(file_name)

def save_benchmarks(file_name='benchmarks.json'):
    with open(file_name, 'w') as f:
        json.dump(driver.all_tests, f,
                  separators=(',',':'))

def chart_url(series_file_name):
    import urlparse, urllib, os
    chart = urlparse.urljoin(
      'file:', urllib.pathname2url(os.path.abspath('chart.html')))
    url_parts = list(urlparse.urlparse(chart))
    url_parts[4] = urllib.urlencode({'f': series_file_name})
    return urlparse.urlunparse(url_parts)

def cmd_open_url_with_params(url):
    return ['osascript', '-e',
            'tell application "Safari" to open location "{0}"'.format(url)]

def open_chart_in_safari(series_file_name='f.json'):
    driver._invoke(cmd_open_url_with_params(chart_url(series_file_name)))

def iters(t, reverse=False, cap=None):
    vary_iterations(t, reverse, cap)
    save_samples(driver.last_run.name, driver.last_run.name + ' iters.json')
    # open_chart_in_safari()
    # driver.results.pop(t)  # FIXME should remove all starting with 't'


def parse_logs(test):
    run_names_and_logs = [(s, '{0}-{1}.log'.format(test, s))
                          for s in ['a', 'b', 'c', 'd']]
    named_results = [(driver.parser.results_from_file(log_file).items()[0][1], run_name)
                     for run_name, log_file in run_names_and_logs]
    the_series = [series(result, result.name + ' i0' + run_name)
                  for result, run_name in named_results]
    return {
        'name': the_series[0]['name'].split()[0],
        'type': 'num_iters',
        'series': the_series}


def save_parsed_samples():
    for test in range (1,472):
        data = parse_logs(test)
        file_name = data['name'] + ' i0_.json'
        with open(file_name, 'w') as f:
            json.dump(data, f, separators=(',',':'))

# TODO diagnostics:
# ignore samples from 1st 1/8s - outliers before stable state?
# runtime Onone under 1 s
# mem stability when varying -num-iters (3 independent runs?)
# measure context switches (voluntary, involuntary) - do they correlate with
#    the qualiy of sampling run?
# O vs Onone has no improvement
# runtime is < 20 us (?)
# runtime is > 2000 us (?)
# startup overhead - visible when running with varying num-iters
# save GIT hash of the build under test in report

# XXX  strangely unstable relations between iterations for various runs:
# 88 DropWhileAnyCollection, 92 DropWhileAnySeqCntRange,
# XXX
# clear startup overhead: 15 ArrayAppendStrings,
# 21 ArrayOfGenericPOD, 23 ArrayOfPOD, 24 ArrayOfRef,
# 68, DropFirstArray,
# 82 DropLastArray, 96 DropWhileArray, ??103 EqualSubstringString??,
# 112 IterateData,
