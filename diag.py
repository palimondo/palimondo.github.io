#!/usr/bin/python
# -*- coding: utf-8 -*-
import json
import subprocess
import gc

from math import log
from Benchmark_Driver import BenchmarkDriver
from compare_perf_tests import PerformanceTestSamples
from compare_perf_tests import PerformanceTestResult
from compare_perf_tests import Sample

class ArgsStub(object):
    """Stub for initializing the BenchmarkDriver"""
    def __init__(self):
        self.benchmarks = '1'
        self.filters = None
        self.tests = ('/Users/mondo/Developer/swift-source/build/'
                      'Ninja-ReleaseAssert/swift-macosx-x86_64/bin')
        self.optimization = 'O'
        self.measure_environment = False

BD = BenchmarkDriver(ArgsStub())

# Manualy control the garbage collection to not interfere with measurements
gc.disable()

def adjusted_1s_samples(runtime, i=1):
    """Number of samples that can be taken in approximately 1 second, based
    on the runtime (microseconds) of one sample taken with `i` iterations."""
    if runtime == 0:
        return 2
    s = 1000000 / float(runtime * i) # samples for 1s run
    s = int(pow(2, round(log(s, 2))))  # rounding to power of 2
    return s if s > 2 else 2  # always take at least 2 samples

def run_args(s, i=1):
    """Generate arguments (s, i) for `run` function that trade the number of
    iterations and samples while maintaining the same running time."""
    while s > 1:
        yield (s, i)
        i = i * 2
        s = s / 2

def run(t, s=3, i=1, verbose=True):  # default s & i are for calibration
    """Run the benchmark and store the result"""
    t = t if isinstance(t, str) else str(t)
    # import time
    # time.sleep(0.8)
    r = BD.run(t, s, i, verbose, measure_environment=True)
    gc.collect()
    BD.last_run = r
    if r.name not in BD.results:
        BD.results[r.name] = r
    else:
        BD.results[r.name].merge(r)
    return r

def num_iters(result):
    """Number of iterations used to measure the samples in this result.
    Based on the assumption that measurements were taken with specified
    `num_iters` constant instead of automatic scaling."""
    return result.samples.samples[0].num_iters

def series(result, name=None):
    """Series dictionary for serialization into JSON"""
    return {
        'name' : name if name else '{0} i{1}'.format(result.name, num_iters(result)),
        'num_iters' : num_iters(result),
        'involuntary_cs' : result.involuntary_cs if hasattr(result, 'involuntary_cs') else None,
        'voluntary_cs' : result.voluntary_cs  if hasattr(result, 'voluntary_cs') else None,
        'max_rss' : result.max_rss  if hasattr(result, 'max_rss') else None,
        'data' : [sample.runtime for sample in result.samples.all_samples]}


def series_data(test):
    """Series data dictionary for serialization into JSON"""
    return {
        'name': test,
        'type': 'num_iters',
        'series': [series(test_result, test_run_name)
                   for test_run_name, test_result in BD.results.items()
                   if test_run_name.startswith(test + ' ')]}

def capped(samples): return min(samples, 4096)


STRATS = ['ten', 'dozen', 'tenR', 'd10', 'd12', 'd10R']

def perform_hidden(measurement, *args):
    BD._invoke(cmd_minimize_terminal(True))
    measurement(*args)
    BD._invoke(cmd_minimize_terminal(False))
    BD._invoke(cmd_notification())

def measure(test, strat, series_name=None):
    series_name = series_name or strat.__name__
    strat(test)
    save_samples(BD.last_run.name,
                 BD.last_run.name + ' ' + series_name + '.json')

def dozen(t):
    ras = list(run_args(adjusted_1s_samples(run(t).min)))[:3]
    ras = list(reversed(ras))
    for suffix in ['a', 'b', 'c', 'd']:
        for (s, i) in ras:
            res = run(t, capped(s), i, True)
            BD.results[res.name + ' i' + str(i) + suffix] = res
            # print res.samples
    # save_samples(BD.last_run.name, BD.last_run.name + ' dozen.json')
    # open_chart_in_safari()

def ten(t):
    suffixes = list('abcdefghij')
    ras = list(run_args(adjusted_1s_samples(run(t).min)))[:2]
    num_series = [10] if len(ras) < 2 else [6, 4]

    for (i, params) in zip(num_series, ras):
        for suffix in suffixes[:i]:
            num_samples, num_iters = params
            res = run(t, capped(num_samples), num_iters, True)
            BD.results[res.name + ' i' + str(num_iters) + suffix] = res
            # print res.samples

    # save_samples(BD.last_run.name, BD.last_run.name + ' d10.json')
    # open_chart_in_safari()

def tenR(t):
    suffixes = list('abcdefghij')
    ras = list(reversed(list(run_args(adjusted_1s_samples(run(t).min)))[:2]))
    num_series = [10] if len(ras) < 2 else [5, 5]

    for (i, params) in zip(num_series, ras):
        for suffix in suffixes[:i]:
            num_samples, num_iters = params
            res = run(t, capped(num_samples), num_iters, True)
            BD.results[res.name + ' i' + str(num_iters) + suffix] = res
            # print res.samples

    # save_samples(BD.last_run.name, BD.last_run.name + ' tenR.json')
    # open_chart_in_safari()

def long(t):
    ras = list(run_args(adjusted_1s_samples(run(t).min)))[:1]
    for suffix in ['a', 'b', 'c', 'd']:
        for (s, i) in ras:
            res = run(t, s * 20, i, True)
            BD.results[res.name + ' i' + str(i) + suffix] = res
            print res.samples
    # save_samples(BD.last_run.name, BD.last_run.name + ' long.json')


def i0(t):
    run(t, s=1)  # don't need calibration, but need dummy result for merging samples
    for suffix in ['a', 'b', 'c', 'd']:
        res = run(t, 20, 0, True)
        BD.results[res.name + ' ' + suffix] = res
        print res.samples
    # save_samples(BD.last_run.name, BD.last_run.name + ' i0.json')
    # open_chart_in_safari()

def sq(t):  # status quo
    run(t, s=1)  # don't need calibration, but need dummy result for merging samples
    for suffix in ['a', 'b', 'c', 'd']:
        for i in range(0, 20):
            res = run(t, 1, 0, True)
            run_name = res.name + ' i0_' + suffix
            if run_name not in BD.results:
                BD.results[run_name] = res
            else:
                s = res.samples.samples[0]
                s = Sample(i, s.num_iters, s.runtime)
                BD.results[run_name].samples.add(s)
                BD.results[run_name].involuntary_cs += res.involuntary_cs
        BD.results[run_name].samples.exclude_outliers()
        print BD.results[run_name].samples
    # save_samples(BD.last_run.name, BD.last_run.name + ' sq.json')
    # open_chart_in_safari()

def cal(s, e):
    for t in range(s, e):
        r = run(t)
        yield (t, adjusted_1s_samples(r.min))

# FIXME AttributeError: 'BenchmarkDriver' object has no attribute 'last_run'
# def save_samples(test=BD.last_run.name, file_name='f.json'):
def save_samples(test, file_name='f.json'):
    with open(file_name, 'w') as f:
        json.dump(series_data(test), f,
                  separators=(',', ':'))  # compact seriaization
    # throw away saved old measurements
    BD.results = {}
    gc.collect()
    # for test_run, _ in BD.results.items():
    #     if test_run.startswith(test + ' '):
    #         BD.results.pop(test_run)

def load_samples(file_name):
    with open(file_name, 'r') as f:
        samples = json.load(f)
    return [load_series(s) for s in samples['series']]

def load_series(s):
    num_iters = s['num_iters']
    ss = PerformanceTestSamples(
        s['name'], [Sample(i, num_iters, runtime)
                    for (i, runtime) in enumerate(s['data'])])
    r = PerformanceTestResult([0, s['name'], ss.count, ss.min, ss.max,
                               ss.mean, ss.sd, ss.median])
    r.samples = ss

    def _set(key):
        if key in s:
            setattr(r, key, s[key])

    map(_set, ['max_rss', 'involuntary_cs', 'voluntary_cs'])
    return r


def save_benchmarks(file_name='benchmarks.json'):
    with open(file_name, 'w') as f:
        json.dump(BD.all_tests, f,
                  separators=(',', ':'))

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

def cmd_speak(message):
    return ['osascript', '-e', 'say "{0}"'.format(message)]

def cmd_notification(notification='Finished', title='Measurement', sound='Glass'):
    return ['osascript', '-e',
            'display notification "{0}" with title "{1}" sound name "{2}"'
            .format(notification, title, sound)]

def cmd_minimize_terminal(minimized):
    return ['osascript',
            '-e', 'tell application "Terminal"',
            '-e', 'set miniaturized of window 1 to {0}'.format(
                'true' if minimized else 'false'),
             '-e', 'end tell']

def open_chart_in_safari(series_file_name='f.json'):
    BD._invoke(cmd_open_url_with_params(chart_url(series_file_name)))

def iters(t, reverse=False, cap=None):
    ras = list(run_args(adjusted_1s_samples(run(t).min)))
    if cap:
        ras = ras[:cap]
    if reverse:
        ras = reversed(ras)
    for (s, i) in ras:
        print i
        res = run(t, s, i, True)
        BD.results[res.name + ' i' + str(i) +
                       ('r' if reverse else '')] = res
        print res
        print res.samples
    # save_samples(BD.last_run.name, BD.last_run.name + ' iters.json')
    # open_chart_in_safari()

def parse_logs(test):
    run_names_and_logs = [(s, '{0}-{1}.log'.format(test, s))
                          for s in ['a', 'b', 'c', 'd']]
    named_results = [(BD.parser.results_from_file(log_file).items()[0][1], run_name)
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

def setup_overhead(results):
    try:
        mins = sorted([(num_iters(r), r.samples.min) for r in results])
        (i, ti) = map(float, mins[0])
        (j, tj) = map(float, next(m for m in mins if m[0] > i))  # next higher num_iters
        setup = (i * j * (ti - tj)) / (j - i)
        ratio = setup / ti
        return (ir(setup), round(ratio, 5))  if setup > 0  else None
    except:
        return None

def test_stats(t, variant, outliers=False):
    t = t if isinstance(t, str) else BD.all_tests[(t - 1)]
    file_name = t + ' ' + variant + '.json'
    results = load_samples(file_name)
    stats = {'name': t, 'variant': variant,
             'num_samples': max([r.samples.count for r in results] or [0]),
             'rawStats' : [format_stats(r) for r in results]}
    if not results:
        stats['cleanStats'] = []
        return stats
    stats['rawStats'].append(format_stats(all_stats(results)))
    for s in results:
        s.samples.exclude_outliers(top_only=True)
    stats['cleanStats'] = [format_stats(r, outliers) for r in results]

    allClean = all_stats(results)
    stats['cleanStats'].append(format_stats(allClean))

    overhead = setup_overhead(results)
    if overhead:
        setup, ratio = overhead
        if ratio > 0.05 or allClean.samples.iqr < setup:
            stats['setup_overhead'] = \
                list(overhead) + [format_stats(all_stats(results, setup))]

    # print t
    return stats

def all_stats(results, setup=0):
    name = results[0].name.split()[0] + (' all' if not setup else ' fixedAll')
    ics, vcs = 0, 0
    pts = PerformanceTestSamples(name)
    for result in results:
        correction = ir(setup / num_iters(result))
        samples = (result.samples.samples if not setup else
                   [Sample(s.i, s.num_iters, s.runtime - correction)
                    for s in result.samples.samples])
        map(pts.add, samples)
        ics += result.involuntary_cs
        vcs += result.voluntary_cs
    _all = PerformanceTestResult(
        [0, name, pts.num_samples, pts.min, pts.max,
         int(pts.mean), int(pts.sd), pts.median])
    _all.samples = pts
    _all.involuntary_cs = ics
    _all.voluntary_cs = vcs

    return _all

def ir(num):
    return int(round(num))

def format_stats(result, outliers=False):
    s, M = result.samples, result.samples.mean
    def pob(r, b):  # percent of base
        return str(ir(float(r) / float(b) * 100)) + '%' if b else 0

    stats = [
        result.name.split()[-1],
        s.count, s.min, s.max, s.range, pob(s.range, s.min), s.q1, s.q3, s.iqr,
        pob(s.iqr, s.median), s.median, ir(s.mean), ir(s.sd), pob(s.sd, s.mean),
        result.involuntary_cs if hasattr(result, 'involuntary_cs') else None,
        result.voluntary_cs if hasattr(result, 'voluntary_cs') else None,
        result.max_rss if hasattr(result, 'max_rss') else None,
        [sample.runtime
         for sample in result.samples.outliers] if outliers else None,
    ]
    # print stats
    return stats

def print_progress(iteration, total, prefix='', suffix='', decimals=1,
                   bar_length=10):
    """
    Call in a loop to create terminal progress bar
    @params:
        iteration   - Required  : current iteration (Int)
        total       - Required  : total iterations (Int)
        prefix      - Optional  : prefix string (Str)
        suffix      - Optional  : suffix string (Str)
        decimals    - Optional  : positive number of decimals in percent complete (Int)
        bar_length  - Optional  : character length of bar (Int)
    """
    import sys
    str_format = "{0:." + str(decimals) + "f}"
    percents = str_format.format(100 * (iteration / float(total)))
    filled_length = int(round(bar_length * iteration / float(total)))
    bar = '█' * filled_length + '-' * (bar_length - filled_length)

    sys.stdout.write('\r%s |%s| %s%s %s' % (prefix, bar, percents, '%', suffix)),

    if iteration == total:
        sys.stdout.write('\n')
    sys.stdout.flush()

CLEAR_TO_EOL = '\033[K'  # Clear to the end of line
CURSOR_UP = '\033[F'  # Cursor up one line

def save_stats(variant, outliers=True):
    total = len(BD.all_tests) - 1
    def stats_with_progress(t, i):
        print_progress(i, total, variant, t + CLEAR_TO_EOL)
        return test_stats(t, variant, outliers)

    stats = [stats_with_progress(t, i) for i, t in enumerate(BD.all_tests)]
    file_name = 'benchmarks ' + variant + '.json'
    print(CURSOR_UP + 'Saving ' + file_name + CLEAR_TO_EOL)
    with open(file_name, 'w') as f:
        json.dump(stats, f,
                  separators=(',', ':'))  # compact seriaization

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
