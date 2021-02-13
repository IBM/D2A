#!/bin/bash

# ffmpeg
# ./autoinferbox.sh /gpfs/r92gpfs02/zhengyu/infer_runs/pipeline/ffmpeg/devign_ffmpeg_commits.txt /gpfs/r92gpfs02/zhengyu/infer_runs/pipeline/ffmpeg/FFmpeg /gpfs/r92gpfs02/zhengyu/infer_runs/output/ffmpeg /dev/shm/$USER pair ffmpeg

./autoinferbox.sh /gpfs/r92gpfs02/zhengyu/infer_runs/pipeline/ffmpeg/latest_commit.txt /gpfs/r92gpfs02/zhengyu/infer_runs/pipeline/ffmpeg/FFmpeg /gpfs/r92gpfs02/zhengyu/infer_runs/output/ffmpeg /dev/shm/$USER pair ffmpeg
