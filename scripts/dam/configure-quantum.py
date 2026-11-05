#!/usr/bin/env python3
"""USER ONLY: run in your DAM browser Terminal, never through an AI agent.

The API key goes directly from a hidden terminal prompt to the IBM SDK.
It is not passed on the command line or printed to stdout.
"""
import getpass
import logging
import os
import sys
from pathlib import Path

from qiskit_ibm_runtime import QiskitRuntimeService


def main():
    if not sys.stdin.isatty():
        print("Open your own DAM Terminal and run this command there; a hidden prompt requires a terminal.")
        return 1
    logging.getLogger("qiskit_ibm_runtime").setLevel(logging.CRITICAL)
    os.umask(0o077)
    print("IBM Quantum Platform — your API key will be stored only in this agent's SDK account file.")
    print("Get the API key and instance CRN at https://quantum.cloud.ibm.com/")
    instance = input("Instance CRN (recommended; Enter for account discovery): ").strip()
    token = getpass.getpass("IBM Quantum API key (hidden): ").strip()
    if not token:
        print("No API key supplied. Nothing was saved.")
        return 1
    try:
        options = {"channel": "ibm_quantum_platform", "token": token}
        if instance:
            options["instance"] = instance
        service = QiskitRuntimeService(**options)
        backends = service.backends(simulator=False)
        if not backends:
            print("No accessible QPUs. Check your account and instance CRN. Nothing was saved.")
            return 1
        QiskitRuntimeService.save_account(**options, overwrite=True, set_as_default=True)
        account_path = Path.home() / ".qiskit/qiskit-ibm.json"
        if account_path.exists():
            account_path.parent.chmod(0o700)
            account_path.chmod(0o600)
        print(f"Connected to IBM Quantum Platform. Accessible QPUs: {len(backends)}. Account saved.")
        print("Return to the agent chat and ask it to run scripts/dam/quantum doctor --online.")
        return 0
    except Exception as error:  # noqa: BLE001 - Never display raw SDK credential errors
        print(f"Connection failed ({type(error).__name__}). Check API key, CRN and DAM network rules; nothing was saved.")
        return 1
    finally:
        token = None


if __name__ == "__main__":
    raise SystemExit(main())
