#!/bin/sh

files=$(find data/*)

echo '================================================================================'
echo 'load pg_normalized'
echo '================================================================================'

time echo "$files" | parallel python3 load_tweets.py --db="postgresql://postgres:pass@localhost:1292" --inputs={}

