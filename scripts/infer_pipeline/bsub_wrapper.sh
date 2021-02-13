#!/bin/bash
output_path=$4
jbsub -m 150G -c 34 -q x86_12h  << EOF
#!/bin/bash
#BSUB -e $output_path/job%J.out
#BSUB -o $output_path/job%J.out
echo "Bsub wrapper $@"
/bin/bash $@
EOF
