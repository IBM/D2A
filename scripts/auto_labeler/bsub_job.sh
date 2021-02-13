#!/bin/bash
bsub -n 1 -W 72:00 << EOF
#!/bin/bash
#BSUB -q excl
#BSUB -e job%J.out
#BSUB -o job%J.out
#BSUB -R "span[ptile=4]"
#BSUB -R "select[hname!='c460c032']"
echo "Bsub wrapper ./run_gen_label.sh"
/bin/bash ./run_gen_label.sh libav
EOF
