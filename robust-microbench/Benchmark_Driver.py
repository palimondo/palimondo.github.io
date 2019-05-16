#!/usr/bin/env python
# -*- coding: utf-8 -*-

# ===--- Benchmark_Driver ------------------------------------------------===//
#
#  This source file is part of the Swift.org open source project
#
#  Copyright (c) 2014 - 2017 Apple Inc. and the Swift project authors
#  Licensed under Apache License v2.0 with Runtime Library Exception
#
#  See https://swift.org/LICENSE.txt for license information
#  See https://swift.org/CONTRIBUTORS.txt for the list of Swift project authors
#
# ===---------------------------------------------------------------------===//
"""
Benchmark_Driver is a tool for running and analysing Swift Benchmarking Suite.

Example:
    $ Benchmark_Driver run

Use `Benchmark_Driver -h` for help on available commands and options.

class `BenchmarkDriver` runs performance tests and impements the `run` COMMAND.
class `BenchmarkDoctor` analyzes performance tests, implements `check` COMMAND.

"""

import argparse
import glob
import logging
import math
import os
import re
import subprocess
import sys
import time

from compare_perf_tests import LogParser

DRIVER_DIR = os.path.dirname(os.path.realpath(__file__))


class BenchmarkDriver(object):
    """Executes tests from Swift Benchmark Suite.

    It's a higher level wrapper for the Benchmark_X family of binaries
    (X = [O, Onone, Osize]).
    """

    def __init__(self, args, tests=None, _subprocess=None, parser=None):
        """Initialize with command line arguments.

        Optional parameters are for injecting dependencies -- used for testing.
        """
        self.args = args
        self._subprocess = _subprocess or subprocess
        self.all_tests = []
        self.test_number = {}
        self.tests = tests or self._get_tests()
        self.parser = parser or LogParser()
        self.results = {}
        # Set a constant hash seed. Some tests are currently sensitive to
        # fluctuations in the number of hash collisions.
        os.environ['SWIFT_DETERMINISTIC_HASHING'] = '1'

    def _invoke(self, cmd):
        return self._subprocess.check_output(
            cmd, stderr=self._subprocess.STDOUT)

    @property
    def test_harness(self):
        """Full path to test harness binary."""
        suffix = (self.args.optimization if hasattr(self.args, 'optimization')
                  else 'O')
        return os.path.join(self.args.tests, "Benchmark_" + suffix)

    def _git(self, cmd):
        """Execute the Git command in the `swift-repo`."""
        return self._invoke(
            ('git -C {0} '.format(self.args.swift_repo) + cmd).split()).strip()

    @property
    def log_file(self):
        """Full path to log file.

        If `swift-repo` is set, log file is tied to Git branch and revision.
        """
        if not self.args.output_dir:
            return None
        log_dir = self.args.output_dir
        harness_name = os.path.basename(self.test_harness)
        suffix = '-' + time.strftime('%Y%m%d%H%M%S', time.localtime())
        if self.args.swift_repo:
            log_dir = os.path.join(
                log_dir, self._git('rev-parse --abbrev-ref HEAD'))  # branch
            suffix += '-' + self._git('rev-parse --short HEAD')  # revision
        return os.path.join(log_dir, harness_name + suffix + '.log')

    @property
    def _cmd_list_benchmarks(self):
        # Use tab delimiter for easier parsing to override the default comma.
        # (The third 'column' is always comma-separated list of tags in square
        # brackets -- currently unused here.)
        return [self.test_harness, '--list', '--delim=\t'] + (
            ['--skip-tags='] if (self.args.benchmarks or
                                 self.args.filters) else [])

    def _get_tests(self):
        """Return a list of performance tests to run."""
        number_name_pairs = [
            line.split('\t')[:2] for line in
            self._invoke(self._cmd_list_benchmarks).split('\n')[1:-1]
        ]
        # unzip list of pairs into 2 lists
        test_numbers, self.all_tests = map(list, zip(*number_name_pairs))
        self.test_number = dict(zip(self.all_tests, test_numbers))
        if self.args.filters:
            return self._tests_matching_patterns()
        if self.args.benchmarks:
            return self._tests_by_name_or_number(test_numbers)
        return self.all_tests

    def _tests_matching_patterns(self):
        regexes = [re.compile(pattern) for pattern in self.args.filters]
        return sorted(list(set([name for pattern in regexes
                                for name in self.all_tests
                                if pattern.match(name)])))

    def _tests_by_name_or_number(self, test_numbers):
        benchmarks = set(self.args.benchmarks)
        number_to_name = dict(zip(test_numbers, self.all_tests))
        tests_by_number = [number_to_name[i]
                           for i in benchmarks.intersection(set(test_numbers))]
        return sorted(list(benchmarks
                           .intersection(set(self.all_tests))
                           .union(tests_by_number)))

    def run(self, test=None, num_samples=None, num_iters=None,
            sample_time=None, verbose=None, measure_memory=False,
            quantile=None):
        """Execute benchmark and gather results."""
        num_samples = num_samples or 0
        num_iters = num_iters or 0  # automatically determine N to run for 1s
        sample_time = sample_time or 0  # default is 1s

        cmd = self._cmd_run(
            test, num_samples, num_iters, sample_time,
            verbose, measure_memory, quantile)
        output = self._invoke(cmd)
        results = self.parser.results_from_string(output)
        return results.items()[0][1] if test else results

    def _cmd_run(self, test, num_samples, num_iters, sample_time,
                 verbose, measure_memory, quantile):
        cmd = [self.test_harness]
        if test:
            cmd.append(test)
        else:
            cmd.extend([self.test_number.get(name, name)
                        for name in self.tests])
        if num_samples > 0:
            cmd.append('--num-samples={0}'.format(num_samples))
        if num_iters > 0:
            cmd.append('--num-iters={0}'.format(num_iters))
        if sample_time > 0:
            cmd.append('--sample-time={0}'.format(sample_time))
        if verbose:
            cmd.append('--verbose')
        if measure_memory:
            cmd.append('--memory')
        if quantile:
            cmd.append('--quantile={0}'.format(quantile))
            cmd.append('--delta')
        return cmd

    def run_independent_samples(self, test):
        """Run benchmark multiple times, gathering independent samples.

        Returns the aggregated result of independent benchmark invocations.
        """
        def merge_results(a, b):
            a.merge(b)
            return a

        return reduce(merge_results,
                      [self.run(test, measure_memory=True,
                                num_iters=1, quantile=20)
                       for _ in range(self.args.independent_samples)])

    def log_results(self, output, log_file=None):
        """Log output to `log_file`.

        Creates `args.output_dir` if it doesn't exist yet.
        """
        log_file = log_file or self.log_file
        dir = os.path.dirname(log_file)
        if not os.path.exists(dir):
            os.makedirs(dir)
        print('Logging results to: %s' % log_file)
        with open(log_file, 'w') as f:
            f.write(output)

    RESULT = '{:>3} {:<40} {:>7} {:>7} {:>6} {:>10} {:>6} {:>7} {:>10}'

    def run_and_log(self, csv_console=True):
        """Run benchmarks and continuously log results to the console.

        There are two console log formats: CSV and justified columns. Both are
        compatible with `LogParser`. Depending on the `csv_console` parameter,
        the CSV log format is either printed to console or returned as a string
        from this method. When `csv_console` is False, the console output
        format is justified columns.
        """
        format = (
            (lambda values: ','.join(values)) if csv_console else
            (lambda values: self.RESULT.format(*values)))  # justified columns

        def console_log(values):
            print(format(values))

        def result_values(r):
            return map(str, [r.test_num, r.name, r.num_samples, r.min,
                             r.samples.q1, r.median, r.samples.q3, r.max,
                             r.max_rss])

        header = ['#', 'TEST', 'SAMPLES', 'MIN(μs)', 'Q1(μs)', 'MEDIAN(μs)',
                  'Q3(μs)', 'MAX(μs)', 'MAX_RSS(B)']
        console_log(header)
        results = [header]
        for test in self.tests:
            result = result_values(self.run_independent_samples(test))
            console_log(result)
            results.append(result)

        print(
            '\nTotal performance tests executed: {0}'.format(len(self.tests)))
        return (None if csv_console else
                ('\n'.join([','.join(r) for r in results]) + '\n'))  # csv_log

    @staticmethod
    def run_benchmarks(args):
        """Run benchmarks and log results."""
        driver = BenchmarkDriver(args)
        csv_log = driver.run_and_log(csv_console=(args.output_dir is None))
        if csv_log:
            driver.log_results(csv_log)
        return 0


class LoggingReportFormatter(logging.Formatter):
    """Format logs as plain text or with colors on the terminal.

    Plain text outputs level, category and massage: 'DEBUG category: Hi!'
    Colored output uses color coding based on the level.
    """

    import logging as log
    colors = {log.DEBUG: '9', log.INFO: '2', log.WARNING: '3', log.ERROR: '1',
              log.CRITICAL: '5'}

    def __init__(self, use_color=False):
        """Specify if report should use colors; defaults to False."""
        super(LoggingReportFormatter, self).__init__('%(message)s')
        self.use_color = use_color

    def format(self, record):
        """Format the log record with level and category."""
        msg = super(LoggingReportFormatter, self).format(record)
        category = ((record.name.split('.')[-1] + ': ') if '.' in record.name
                    else '')
        return ('\033[1;3{0}m{1}{2}\033[1;0m'.format(
            self.colors[record.levelno], category, msg) if self.use_color else
            '{0} {1}{2}'.format(record.levelname, category, msg))


class MarkdownReportHandler(logging.StreamHandler):
    r"""Write custom formatted messages from BenchmarkDoctor to the stream.

    It works around StreamHandler's hardcoded '\n' and handles the custom
    level and category formatting for BenchmarkDoctor's check report.
    """

    def __init__(self, stream):
        """Initialize the handler and write a Markdown table header."""
        super(MarkdownReportHandler, self).__init__(stream)
        self.setLevel(logging.INFO)
        self.stream.write('\n✅  | Benchmark Check Report\n---|---')
        self.stream.flush()

    levels = {logging.WARNING: '\n⚠️', logging.ERROR: '\n⛔️',
              logging.INFO: ' <br><sub> '}
    categories = {'naming': '🔤', 'runtime': '⏱', 'memory': 'Ⓜ️'}
    quotes_re = re.compile("'")

    def format(self, record):
        msg = super(MarkdownReportHandler, self).format(record)
        return (self.levels.get(record.levelno, '') +
                ('' if record.levelno == logging.INFO else
                 self.categories.get(record.name.split('.')[-1], '') + ' | ') +
                self.quotes_re.sub('`', msg))

    def emit(self, record):
        msg = self.format(record)
        stream = self.stream
        try:
            if (isinstance(msg, unicode) and
                    getattr(stream, 'encoding', None)):
                stream.write(msg.encode(stream.encoding))
            else:
                stream.write(msg)
        except UnicodeError:
            stream.write(msg.encode("UTF-8"))
        self.flush()

    def close(self):
        self.stream.write('\n\n')
        self.stream.flush()
        super(MarkdownReportHandler, self).close()


class BenchmarkDoctor(object):
    """Checks that the benchmark conforms to the standard set of requirements.

    Benchmarks that are part of Swift Benchmark Suite are required to follow
    a set of rules that ensure quality measurements. These include naming
    convention, robustness when varying execution parameters like
    `num-iters` and `num-samples` (no setup overhead, constant memory
    consumption).
    """

    log = logging.getLogger('BenchmarkDoctor')
    log_naming = log.getChild('naming')
    log_runtime = log.getChild('runtime')
    log_memory = log.getChild('memory')
    log.setLevel(logging.DEBUG)

    def __init__(self, args, driver=None):
        """Initialize with command line parameters.

        Optional `driver` parameter for injecting dependency; used for testing.
        """
        super(BenchmarkDoctor, self).__init__()
        self.driver = driver or BenchmarkDriver(args)
        self.results = {}

        if hasattr(args, 'markdown') and args.markdown:
            self.console_handler = MarkdownReportHandler(sys.stdout)
        else:
            self.console_handler = logging.StreamHandler(sys.stdout)
            self.console_handler.setFormatter(
                LoggingReportFormatter(use_color=sys.stdout.isatty()))
            self.console_handler.setLevel(logging.DEBUG if args.verbose else
                                          logging.INFO)
        self.log.addHandler(self.console_handler)
        self.log.debug('Checking tests: %s', ', '.join(self.driver.tests))
        self.requirements = [
            self._name_matches_benchmark_naming_convention,
            self._name_is_at_most_40_chars_long,
            self._no_setup_overhead,
            self._reasonable_setup_time,
            self._optimized_runtime_in_range,
            self._constant_memory_use
        ]

    def __del__(self):
        """Close log handlers on exit."""
        for handler in list(self.log.handlers):
            handler.close()
        self.log.removeHandler(self.console_handler)

    benchmark_naming_convention_re = re.compile(r'[A-Z][a-zA-Z0-9\-.!?]+')
    camel_humps_re = re.compile(r'[a-z][A-Z]')

    @staticmethod
    def _name_matches_benchmark_naming_convention(measurements):
        name = measurements['name']
        match = BenchmarkDoctor.benchmark_naming_convention_re.match(name)
        matched = match.group(0) if match else ''
        composite_words = len(BenchmarkDoctor.camel_humps_re.findall(name)) + 1

        if name != matched:
            BenchmarkDoctor.log_naming.error(
                "'%s' name doesn't conform to benchmark naming convention.",
                name)
            BenchmarkDoctor.log_naming.info(
                'See http://bit.ly/BenchmarkNaming')

        if composite_words > 4:
            BenchmarkDoctor.log_naming.warning(
                "'%s' name is composed of %d words.", name, composite_words)
            BenchmarkDoctor.log_naming.info(
                "Split '%s' name into dot-separated groups and variants. "
                "See http://bit.ly/BenchmarkNaming", name)

    @staticmethod
    def _name_is_at_most_40_chars_long(measurements):
        name = measurements['name']

        if len(name) > 40:
            BenchmarkDoctor.log_naming.error(
                "'%s' name is %d characters long.", name, len(name))
            BenchmarkDoctor.log_naming.info(
                'Benchmark name should not be longer than 40 characters.')

    @staticmethod
    def _select(measurements, num_iters=None, opt_level='O'):
        prefix = measurements['name'] + ' ' + opt_level
        prefix += '' if num_iters is None else (' i' + str(num_iters))
        return [series for name, series in measurements.items()
                if name.startswith(prefix)]

    @staticmethod
    def _optimized_runtime_in_range(measurements):
        name = measurements['name']
        setup, ratio = BenchmarkDoctor._setup_overhead(measurements)
        setup = 0 if ratio < 0.05 else setup
        runtime = min(
            [(result.samples.min - correction) for i_series in
             [BenchmarkDoctor._select(measurements, num_iters=i)
              for correction in [(setup / i) for i in [1, 2]]
              ] for result in i_series])

        threshold = 1000
        if threshold < runtime:
            log = (BenchmarkDoctor.log_runtime.warning if runtime < 10000 else
                   BenchmarkDoctor.log_runtime.error)
            caveat = '' if setup == 0 else ' (excluding the setup overhead)'
            log("'%s' execution took at least %d μs%s.", name, runtime, caveat)

            def factor(base):  # suitable divisior that's integer power of base
                return int(pow(base, math.ceil(
                    math.log(runtime / float(threshold), base))))

            BenchmarkDoctor.log_runtime.info(
                "Decrease the workload of '%s' by a factor of %d (%d), to be "
                "less than %d μs.", name, factor(2), factor(10), threshold)

        threshold = 20
        if runtime < threshold:
            log = (BenchmarkDoctor.log_runtime.error if runtime == 0 else
                   BenchmarkDoctor.log_runtime.warning)
            log("'%s' execution took %d μs.", name, runtime)

            BenchmarkDoctor.log_runtime.info(
                "Ensure the workload of '%s' has a properly measurable size"
                " (runtime > %d μs) and is not eliminated by the compiler (use"
                " `blackHole` function if necessary)." if runtime == 0 else
                "Increase the workload of '%s' to be more than %d μs.",
                name, threshold)

    @staticmethod
    def _setup_overhead(measurements):
        select = BenchmarkDoctor._select
        ti1, ti2 = [float(min(mins)) for mins in
                    [[result.samples.min for result in i_series]
                     for i_series in
                     [select(measurements, num_iters=i) for i in [1, 2]]]]
        setup = (int(round(2.0 * (ti1 - ti2))) if ti2 > 20  # limit of accuracy
                 else 0)
        ratio = (setup / ti1) if ti1 > 0 else 0
        return (setup, ratio)

    @staticmethod
    def _no_setup_overhead(measurements):
        setup, ratio = BenchmarkDoctor._setup_overhead(measurements)
        if ratio > 0.05:
            BenchmarkDoctor.log_runtime.error(
                "'%s' has setup overhead of %d μs (%.1f%%).",
                measurements['name'], setup, round((100 * ratio), 1))
            BenchmarkDoctor.log_runtime.info(
                'Move initialization of benchmark data to the `setUpFunction` '
                'registered in `BenchmarkInfo`.')

    @staticmethod
    def _reasonable_setup_time(measurements):
        setup = min([result.setup
                     for result in BenchmarkDoctor._select(measurements)])
        if 200000 < setup:  # 200 ms
            BenchmarkDoctor.log_runtime.error(
                "'%s' setup took at least %d μs.",
                measurements['name'], setup)
            BenchmarkDoctor.log_runtime.info(
                'The `setUpFunction` should take no more than 200 ms.')

    @staticmethod
    def _constant_memory_use(measurements):
        select = BenchmarkDoctor._select
        (min_i1, max_i1), (min_i2, max_i2) = [
            (min(memory_use), max(memory_use)) for memory_use in
            [[r.mem_pages for r in i_series] for i_series in
             [select(measurements, num_iters=i) for i in
              [1, 2]]]]
        range_i1, range_i2 = max_i1 - min_i1, max_i2 - min_i2
        normal_range = 15  # pages
        name = measurements['name']
        more_info = False

        if abs(min_i1 - min_i2) > max(range_i1, range_i2, normal_range):
            more_info = True
            BenchmarkDoctor.log_memory.error(
                "'%s' varies the memory footprint of the base "
                "workload depending on the `num-iters`.", name)

        if max(range_i1, range_i2) > normal_range:
            more_info = True
            BenchmarkDoctor.log_memory.warning(
                "'%s' has very wide range of memory used between "
                "independent, repeated measurements.", name)

        if more_info:
            BenchmarkDoctor.log_memory.info(
                "'%s' mem_pages [i1, i2]: min=[%d, %d] 𝚫=%d R=[%d, %d]",
                name,
                *[min_i1, min_i2, abs(min_i1 - min_i2), range_i1, range_i2])

    @staticmethod
    def _adjusted_1s_samples(runtime):
        u"""Return sample count that can be taken in approximately 1 second.

        Based on the runtime (μs) of one sample taken with num-iters=1.
        """
        if runtime == 0:
            return 2
        s = 1000000 / float(runtime)  # samples for 1s run
        s = int(pow(2, round(math.log(s, 2))))  # rounding to power of 2
        return s if s > 2 else 2  # always take at least 2 samples

    def measure(self, benchmark):
        """Measure benchmark with varying iterations and optimization levels.

        Returns a dictionary with benchmark name and `PerformanceTestResult`s.
        """
        self.log.debug('Calibrating num-samples for {0}:'.format(benchmark))
        r = self.driver.run(benchmark, num_samples=3, num_iters=1,
                            verbose=True)  # calibrate
        num_samples = self._adjusted_1s_samples(r.samples.min)

        def capped(s):
            return min(s, 200)
        run_args = [(capped(num_samples), 1), (capped(num_samples / 2), 2)]
        opts = self.driver.args.optimization
        opts = opts if isinstance(opts, list) else [opts]
        self.log.debug(
            'Runtime {0} μs yields {1} adjusted samples per second.'.format(
                r.samples.min, num_samples))
        self.log.debug(
            'Measuring {0}, 5 x i1 ({1} samples), 5 x i2 ({2} samples)'.format(
                benchmark, run_args[0][0], run_args[1][0]))

        measurements = dict(
            [('{0} {1} i{2}{3}'.format(benchmark, o, i, suffix),
              self.driver.run(benchmark, num_samples=s, num_iters=i,
                              verbose=True, measure_memory=True))
             for o in opts
             for s, i in run_args
             for suffix in list('abcde')
             ]
        )
        measurements['name'] = benchmark
        return measurements

    def analyze(self, benchmark_measurements):
        """Analyze whether benchmark fullfills all requirtements."""
        self.log.debug('Analyzing %s', benchmark_measurements['name'])
        for rule in self.requirements:
            rule(benchmark_measurements)

    def check(self):
        """Measure and analyse all enabled tests."""
        for test in self.driver.tests:
            self.analyze(self.measure(test))

    @staticmethod
    def run_check(args):
        """Validate benchmarks conform to health rules, report violations."""
        doctor = BenchmarkDoctor(args)
        doctor.check()
        # TODO non-zero error code when errors are logged
        # See https://stackoverflow.com/a/31142078/41307
        return 0


def format_name(log_path):
    """Return the filename and directory for a log file."""
    return '/'.join(log_path.split('/')[-2:])


def compare_logs(compare_script, new_log, old_log, log_dir, opt):
    """Return diff of log files at paths `new_log` and `old_log`."""
    print('Comparing %s %s ...' % (format_name(old_log), format_name(new_log)))
    subprocess.call([compare_script, '--old-file', old_log,
                    '--new-file', new_log, '--format', 'markdown',
                     '--output', os.path.join(log_dir, 'latest_compare_{0}.md'
                                              .format(opt))])


def compare(args):
    log_dir = args.log_dir
    compare_script = args.compare_script
    baseline_branch = args.baseline_branch
    current_branch = \
        BenchmarkDriver(args, tests=[''])._git('rev-parse --abbrev-ref HEAD')
    current_branch_dir = os.path.join(log_dir, current_branch)
    baseline_branch_dir = os.path.join(log_dir, baseline_branch)

    if current_branch != baseline_branch and \
       not os.path.isdir(baseline_branch_dir):
        print(('Unable to find benchmark logs for {baseline_branch} branch. ' +
               'Set a baseline benchmark log by passing --benchmark to ' +
               'build-script while on {baseline_branch} branch.')
              .format(baseline_branch=baseline_branch))
        return 1

    recent_logs = {}
    for branch_dir in [current_branch_dir, baseline_branch_dir]:
        for opt in ['O', 'Onone']:
            recent_logs[os.path.basename(branch_dir) + '_' + opt] = sorted(
                glob.glob(os.path.join(
                    branch_dir, 'Benchmark_' + opt + '-*.log')),
                key=os.path.getctime, reverse=True)

    if current_branch == baseline_branch:
        if len(recent_logs[baseline_branch + '_O']) > 1 and \
           len(recent_logs[baseline_branch + '_Onone']) > 1:
            compare_logs(compare_script,
                         recent_logs[baseline_branch + '_O'][0],
                         recent_logs[baseline_branch + '_O'][1],
                         log_dir, 'O')
            compare_logs(compare_script,
                         recent_logs[baseline_branch + '_Onone'][0],
                         recent_logs[baseline_branch + '_Onone'][1],
                         log_dir, 'Onone')
        else:
            print(('{baseline_branch}/{baseline_branch} comparison ' +
                   'skipped: no previous {baseline_branch} logs')
                  .format(baseline_branch=baseline_branch))
    else:
        # TODO: Check for outdated baseline branch log
        if len(recent_logs[current_branch + '_O']) == 0 or \
           len(recent_logs[current_branch + '_Onone']) == 0:
            print('branch sanity failure: missing branch logs')
            return 1

        if len(recent_logs[current_branch + '_O']) == 1 or \
           len(recent_logs[current_branch + '_Onone']) == 1:
            print('branch/branch comparison skipped: no previous branch logs')
        else:
            compare_logs(compare_script,
                         recent_logs[current_branch + '_O'][0],
                         recent_logs[current_branch + '_O'][1],
                         log_dir, 'O')
            compare_logs(compare_script,
                         recent_logs[current_branch + '_Onone'][0],
                         recent_logs[current_branch + '_Onone'][1],
                         log_dir, 'Onone')

        if len(recent_logs[baseline_branch + '_O']) == 0 or \
           len(recent_logs[baseline_branch + '_Onone']) == 0:
            print(('branch/{baseline_branch} failure: no {baseline_branch} ' +
                   'logs')
                  .format(baseline_branch=baseline_branch))
            return 1
        else:
            compare_logs(compare_script,
                         recent_logs[current_branch + '_O'][0],
                         recent_logs[baseline_branch + '_O'][0],
                         log_dir, 'O')
            compare_logs(compare_script,
                         recent_logs[current_branch + '_Onone'][0],
                         recent_logs[baseline_branch + '_Onone'][0],
                         log_dir, 'Onone')

        # TODO: Fail on large regressions

    return 0


def positive_int(value):
    """Verify the value is a positive integer."""
    ivalue = int(value)
    if not (ivalue > 0):
        raise ValueError
    return ivalue


def parse_args(args):
    """Parse command line arguments and set default values."""
    parser = argparse.ArgumentParser(
        epilog='Example: ./Benchmark_Driver run -i 5 -f Prefix -f .*Suffix.*'
    )
    subparsers = parser.add_subparsers(
        title='Swift benchmark driver commands',
        help='See COMMAND -h for additional arguments', metavar='COMMAND')

    shared_benchmarks_parser = argparse.ArgumentParser(add_help=False)
    benchmarks_group = shared_benchmarks_parser.add_mutually_exclusive_group()
    benchmarks_group.add_argument(
        'benchmarks',
        default=[],
        help='benchmark to run (default: all)', nargs='*', metavar="BENCHMARK")
    benchmarks_group.add_argument(
        '-f', '--filter', dest='filters', action='append',
        help='run all tests whose name match regular expression PATTERN, ' +
        'multiple filters are supported', metavar="PATTERN")
    shared_benchmarks_parser.add_argument(
        '-t', '--tests',
        help='directory containing Benchmark_O{,none,size} ' +
        '(default: DRIVER_DIR)',
        default=DRIVER_DIR)
    shared_benchmarks_parser.add_argument(
        '-o', '--optimization',
        metavar='OPT',
        choices=['O', 'Onone', 'Osize'],
        help='optimization level to use: {O,Onone,Osize}, (default: O)',
        default='O')

    run_parser = subparsers.add_parser(
        'run',
        help='Run benchmarks and output results to stdout',
        parents=[shared_benchmarks_parser])
    run_parser.add_argument(
        '-i', '--independent-samples',
        help='number of times to run each test (default: 1)',
        type=positive_int, default=1)
    run_parser.add_argument(
        '--output-dir',
        help='log results to directory (default: no logging)')
    run_parser.add_argument(
        '--swift-repo',
        help='absolute path to the Swift source repository')
    run_parser.set_defaults(func=BenchmarkDriver.run_benchmarks)

    check_parser = subparsers.add_parser(
        'check',
        help='',
        parents=[shared_benchmarks_parser])
    check_group = check_parser.add_mutually_exclusive_group()
    check_group.add_argument(
        '-v', '--verbose', action='store_true',
        help='show more details during benchmark analysis')
    check_group.add_argument(
        '-md', '--markdown', action='store_true',
        help='format report as Markdown table')
    check_parser.set_defaults(func=BenchmarkDoctor.run_check)

    compare_parser = subparsers.add_parser(
        'compare',
        help='Compare benchmark results')
    compare_parser.add_argument(
        '--log-dir', required=True,
        help='directory containing benchmark logs')
    compare_parser.add_argument(
        '--swift-repo', required=True,
        help='absolute path to the Swift source repository')
    compare_parser.add_argument(
        '--compare-script', required=True,
        help='absolute path to compare script')
    compare_parser.add_argument(
        '--baseline-branch', default='master',
        help='attempt to compare results to baseline results for specified '
             'branch (default: master)')
    compare_parser.set_defaults(func=compare)

    return parser.parse_args(args)


def main():
    """Parse command line arguments and execute the specified COMMAND."""
    args = parse_args(sys.argv[1:])
    return args.func(args)


if __name__ == '__main__':
    exit(main())
