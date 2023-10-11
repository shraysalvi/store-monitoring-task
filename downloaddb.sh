#!/bin/bash

# Check if db.sqlite3 exists in the current directory
if [ ! -f db.sqlite3 ]; then
    echo "Database not found. Downloading..."
    gdown https://drive.google.com/uc?id=1pFeXdQYQekATfYUjJcQGawBsUIeuKGjH
fi

if [ ! -d data ]; then
    gdown --folder https://drive.google.com/drive/u/1/folders/1GQmDo74jCy4zSn4X_VUjgdfQHJfUJQy7
fi