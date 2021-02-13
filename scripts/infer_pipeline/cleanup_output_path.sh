#!/bin/bash

if [ -z $2 ]; then
  echo "usage: $0 <output_path> <single_or_pair>"
  exit
fi

output_path=$1
single_or_pair=$2

if [ ! "$single_or_pair" == "single" ]; then
  checkDir="differential"
else
  checkDir="curr/report.html"
fi


for dir in $(ls $output_path/*/*|grep -v ":"); do
  full_path="$output_path/${dir:0:1}/${dir:1:1}/$dir"

  if [ ! -d "$full_path/$checkDir" ]; then
    #echo "Removing $full_path"
    rm -rf $full_path
  fi
done
echo "Cleanup done."
