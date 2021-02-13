#!/bin/bash
bsub -n 1 -W 72:00 << EOF
#!/bin/bash
#BSUB -q excl
#BSUB -e job%J.out
#BSUB -o job%J.out
#BSUB -R "span[ptile=4]"
#BSUB -R "select[hname!='c460c032']"
echo "Bsub wrapper ./run_extractor.sh"
/bin/bash ./run_extractor.sh ffmpeg labeler_0 tmp_outputs/ffmpeg
EOF
