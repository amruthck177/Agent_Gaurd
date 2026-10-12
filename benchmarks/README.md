# AgentGuard 2.0 Benchmarks & Security Tests

This directory contains test cases and evaluation scripts for measuring gateway performance and enforcement accuracy.

- `cases.json`: 30+ test cases covering legitimate operations and security violations.
- `run_benchmarks.py`: Benchmark runner measuring unauthorized executions, mismatch detection rate, false-block rate, and added latency.
- `results.json`: Output produced strictly by `run_benchmarks.py`.
- `results.txt`: Formatted results for the presentation deck.
