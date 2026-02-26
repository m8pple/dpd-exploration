#!/usr/bin/env python3
import sys
import argparse
from dataset import command_line_dataset_open_helper
import numpy as np
import numpy.linalg
import math

if __name__=="__main__":

    parser=argparse.ArgumentParser(
        "dataset_list_tags.py"
    )
    parser.add_argument("dataset_dir_or_dmpci_template")
    parser.add_argument("--default_dataset_root", nargs="?", default="dpd_datasets", help="Default directory to put datasets in.")
    
    args=parser.parse_args()

    (dataset,dataset_dir)=command_line_dataset_open_helper(args.dataset_dir_or_dmpci_template, args.default_dataset_root)

    if dataset.matrix==None:
        sys.stderr.write("Dataset is empty.\n")
        sys.exit(1)

    n=dataset.matrix.nExperiments
    print(f"Total samples : {n}")

    global_min_min_l2=1e10
    global_sum_min_l2=0
    global_max_min_l2=0

    data=dataset.matrix.configurations[0:n,:]
    for i in range(0,n):
        deltas = data - data[i,:]
        l2 = numpy.linalg.norm(deltas, axis=1)
        assert l2.shape==(n,), f"n={n}, Shape = {l2.shape}"
        l2[i] = np.nan

        min_l2 = np.nanmin(l2)

        global_min_min_l2 = min( global_min_min_l2, min_l2 )
        global_sum_min_l2 += min_l2
        global_max_min_l2 = max( global_max_min_l2, min_l2 )
        

    print(f"Param distance : min={global_min_min_l2}, avg={global_sum_min_l2/n}, max={global_max_min_l2} ")