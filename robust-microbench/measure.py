#!/usr/bin/python
# -*- coding: utf-8 -*-

import argparse
from multiprocessing import Pool

from diag import BD, measure_series, save_stats, perform_hidden
from diag import series_ten, series_tenR, series_dozen  # , series_iters
from diag import print_progress, CLEAR_TO_EOL


argparser = argparse.ArgumentParser()
argparser.add_argument('series', type=str, choices=['a', 'b', 'c', 'd', 'e'],
                       metavar='Series', help='Series to measure')
args = argparser.parse_args()


def measure_strat(args):
    """Top level function called by worker processes from the Pool."""
    return measure_series(*args)


named_strats = zip(['10', '10R', '12'],
                   [series_ten, series_tenR, series_dozen])
BD.args.optimization = 'O'
# BD.args.optimization = 'Onone'
strats = [(strat, args.series + name) for name, strat in named_strats]
# strats = [(strat, 'a' + name + 'n') for name, strat in named_strats]
# strats = [(series_iters, 'iters')]

# tests = range(1, 4)  # save_stats will crash if these are not all tests
tests = range(1, len(BD.all_tests) + 1)
processes = {'a': 1, 'b': 1, 'c': 2, 'd': 3, 'e': 4}
pool = Pool(processes=processes[args.series])

print("Starting measurement...")

# The a Series is measured with minimized Terminal window:
if args.series == 'a':
    perform_hidden(lambda: pool.map(measure_strat, [(t, s[0], s[1]) for s in
                                                    strats for t in tests]))
    perform_hidden(lambda: [save_stats(s) for x, s in strats])

# The b-e Series are measured with open Terminal window, display progress bar:
else:
    total = len(tests)
    for s in strats:
        for i, t in enumerate(pool.imap(measure_strat, [(t, s[0], s[1])
                                                        for t in tests]), 1):
            print_progress(i, total, s[1], '{0!s}/{1!s} {2}{3}'
                           .format(i, total, t, CLEAR_TO_EOL))
        save_stats(s[1])
