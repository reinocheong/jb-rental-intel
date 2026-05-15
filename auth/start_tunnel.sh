#!/bin/bash
# Try with explicit port request for consistency
~/.local/bin/bore local 8777 --to bore.pub --port 44200 >/tmp/bore_stdout.txt 2>/tmp/bore_stderr.txt
