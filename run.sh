#!/bin/bash

if [ $# -eq 0 ]; then
    echo "Please provide a script as an argument."
    exit 1
fi

script="$1"
log_file="${script%.*}.log"

if [ ! -f "$script" ]; then
    echo "Script '$script' does not exist."
    exit 1
fi

if [ -f "$log_file" ]; then
    echo "Log file '$log_file' already exists. Please choose a different script."
    exit 1
fi

bash "$script" | while IFS= read -r line; do
    timestamp=$(date +"%Y-%m-%d %H:%M:%S")
    echo "[$timestamp] $line"
    echo "[$timestamp] $line" >> "$log_file"
done
