#!/bin/bash

time ./dataset_generator.py $1 $2 $3 &> process_$1.log
