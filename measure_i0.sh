#!/usr/bin/env bash
TIME="$(which time)"
for i in {1..471}; do
  for s in a b c d; do
    # echo "($TIME -lp ./Benchmark_O --num-samples=20 --verbose $i) &> $i-$s.log"
  ($TIME -lp ./Benchmark_O --num-samples=20 --verbose $i) &> $i-$s.log
  done
done
