#!/bin/bash
# Function to run a command or fail with an error message
run_or_fail() {
    local error_message=$1
    shift
    "$@"
    local status=$?
    if [ $status -ne 0 ]; then
        echo "Error: $error_message"
        exit $status
    fi
}