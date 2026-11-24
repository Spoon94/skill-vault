"""Deterministic offline guard for unit tests that load scripts/hao.

Every test module installs this immediately after loading hao. Tests that
need herdr behavior must patch hao.run_herdr (or call restore_real_herdr
for a deliberate PATH-shim integration test).
"""
import os


def install_offline_guard(module):
    real = module.run_herdr
    calls = []

    def offline(args, machine=None):
        calls.append((list(args), machine))
        summary = " ".join(str(a) for a in args[:2])
        return 8, "", f"offline test guard: herdr unavailable ({summary})"

    module._TEST_REAL_RUN_HERDR = real
    module._TEST_HERDR_CALLS = calls
    module.run_herdr = offline
    return module


def restore_real_herdr(module):
    module.run_herdr = module._TEST_REAL_RUN_HERDR
    return module
