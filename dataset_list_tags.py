#!/usr/bin/env python3
import sys
import argparse
from dataset import command_line_dataset_open_helper

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
    
    for (tag,ids) in dataset.matrix.tags_to_indices.items():
        print(f"{tag} : {len(ids)}")
