#!/bin/sh
# usage: run_job.sh name < code ; waits for completion and prints log
Q=/c/Capstone1/matlab_furuta/swingup_ppo/queue
{ echo "rehash; clear functions; clear classes;"; cat; } > $Q/tmp_$1.m && mv $Q/tmp_$1.m $Q/job_$1.m
while [ ! -f $Q/job_$1.done.log ]; do sleep 2; done
cat $Q/job_$1.done.log
