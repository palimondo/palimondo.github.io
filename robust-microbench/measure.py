#!/usr/bin/python
# -*- coding: utf-8 -*-

from multiprocessing import Pool

from diag import BD, measure_series, save_stats  # , perform_hidden
from diag import series_ten, series_tenR, series_dozen  # , series_iters
from diag import print_progress, CLEAR_TO_EOL


def measure_strat(args):
    """Top level function called by worker processes from the Pool."""
    return measure_series(*args)


named_strats = zip(['10', '10R', '12'],
                   [series_ten, series_tenR, series_dozen])
# TODO Configuration:
# 1) Choose the optimization level to measure
# 2) Select and name the measurement strategies
# 3) Set the desired concurrency with the Pool's `processes` parameter
# 4) Uncomment the corresponding measurement process (hidden or visible
#    Terminal window)
BD.args.optimization = 'O'
# BD.args.optimization = 'Onone'
strats = [(strat, 'c' + name) for name, strat in named_strats]
# strats = [(strat, 'a' + name + 'n') for name, strat in named_strats]
# strats = [(series_iters, 'iters')]

# tests = range(1, 4)  # save_stats will crash if these are not all tests
tests = range(1, len(BD.all_tests) + 1)
pool = Pool(processes=2)  # processes for series: a,b=1 c=2, d=3, e=

# # The a Series is measured with minimized Terminal window:
# perform_hidden(lambda: pool.map(measure_strat, [(t, s[0], s[1]) for s in
#                                                 strats for t in tests]))
# perform_hidden(lambda: [save_stats(s) for x, s in strats])

print("Starting measurement...")
# The b-e Series are measured with open Terminal window, display progress bar:
total = len(tests)
for s in strats:
    for i, t in enumerate(pool.imap(measure_strat, [(t, s[0], s[1])
                                                    for t in tests]), 1):
        print_progress(i, total, s[1],
                       '{0!s}/{1!s} {2}{3}'.format(i, total, t, CLEAR_TO_EOL))
    save_stats(s[1])
