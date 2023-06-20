#!/usr/bin/env python3
import sys
import argparse
import uuid
from pathlib import Path
import subprocess
import shutil
import random
from dataclasses import dataclass
import multiprocessing
import os
import bz2
import zipfile
import tempfile
from contextlib import ExitStack

from dataset import DMPCITemplate, Dataset, parse_dmpcas, command_line_dataset_open_helper

@dataclass
class RunConfig:
    template:DMPCITemplate
    dpd_path:Path
    working_dir:Path
    output_dir:Path
    render_povray:bool = False
    keep_pov:bool = False
    keep_rst:bool = False
    keep_dat:bool = False
    preserve_working:bool = False
    tags:str = ""

def add_matching_files(dir:Path, pattern:str, dst_dir:str, dst_zip:zipfile.ZipFile):
    assert dir.is_dir()
    for f in dir.glob(pattern):
        assert f.is_file()
        data=dst_zip.write(f, f"{dst_dir}/{f.name}")

def compress_and_add_matching_files(dir:Path, pattern:str, dst_dir:str, dst_zip:zipfile.ZipFile):
    assert dir.is_dir()
    for f in dir.glob(pattern):
        assert f.is_file()
        with open(f, "rb") as src:
            data=src.read()
        data=bz2.compress(data)
        dst_zip.writestr( f"{dst_dir}/{f.name}.bz2", data, compress_type=zipfile.ZIP_STORED )

def run_one(config:RunConfig):
    seed=random.randint(1, 2**64-1)

    id=f"sample_{seed:016x}"

    sys.stderr.write(f"Starting {id}\n")

    private_working_dir=config.working_dir / id
    private_working_dir.mkdir()

    params=config.template.create_parameters(seed)
    dmpci_text=config.template.substitute_parameters(params)

    with open(private_working_dir / f"dmpci.{id}", "wt" ) as dst:
        dst.write(dmpci_text)

    with open(private_working_dir / "dpd.log", "wt") as log_dst:
        res=subprocess.run(
            [str(config.dpd_path), id],
            cwd=str(private_working_dir),
            stderr=subprocess.STDOUT,
            stdout=log_dst
        )
        assert res.returncode == 0

    if config.render_povray:
        for i in private_working_dir.glob("*.pov"):
            sys.stderr.write(f"Rendering {i}\n")
            with open( i.parent / (i.name+".povray.log"), "wt") as log_dst:
                subprocess.run(
                    ["povray", f"{str(i.name)}", "-W800", "-H600" ],
                    cwd=str(private_working_dir),
                    stdout=log_dst,
                    stderr=subprocess.STDOUT
                )

    db=parse_dmpcas(config.template, id,  private_working_dir, config.tags)
    db.save(private_working_dir / f"{id}.hdf5")
    
    with zipfile.ZipFile(config.working_dir / f"{id}.zip", "x", compression=zipfile.ZIP_DEFLATED) as zip:
        zip.mkdir(id)
        to_add=[f"{prefix}.{id}" for prefix in ["dmpci", "dmpcas", "dmpchs", "dmpcis", "dmpcls"]]
        for filename in to_add:
            zip.write(private_working_dir/filename, f"{id}/{filename}")

        zip.write( private_working_dir / f"{id}.hdf5", f"{id}/{id}.hdf5" )

        if config.render_povray:
            add_matching_files(private_working_dir, "*.png", id, zip)
        if config.keep_dat:
            compress_and_add_matching_files(private_working_dir, "*.dat", id, zip)
        if config.keep_pov:
            compress_and_add_matching_files(private_working_dir, "*.pov", id, zip)
        if config.keep_rst:
            compress_and_add_matching_files(private_working_dir, "*.rst", id, zip)

    # Copy it in in one go, so that it is either there or not
    (config.working_dir / f"{id}.zip").rename( config.output_dir / f"{id}.zip" )

    if not config.preserve_working:
        shutil.rmtree(private_working_dir)

    sys.stderr.write(f"Finished {id}\n")


if __name__=="__main__":

    parser=argparse.ArgumentParser(
        "dataset_run_samples.py"
    )
    parser.add_argument("dataset_dir_or_dmpci_template")
    parser.add_argument("--default_dataset_root", nargs="?", default="dpd_datasets", help="Default directory to put datasets in.")
    parser.add_argument("--dpd-path", default="dpd", type=str, help="Give the path to the osprey dpd executable, or the name of a comand that is accessible on PATH.")
    parser.add_argument("--tags", default="random", type=str, help='List of comma separated tags to assigned to samples.')
    parser.add_argument("--repeats", default=1, type=int, help='Number of random simulation runs to perform.')
    parser.add_argument("--num-processes", default="1", type=str, help="Either integer number, 'max' for number of CPUs, 'halfmax' for number of CPUs/2.")
    parser.add_argument("--working-dir", default=None, help="Directory to create temporary directories in. If nothing is specified then python3 tempfile.TemporaryDirectory will be used.")
    parser.add_argument("--render-povray", default=False, action='store_true', help="Render the pov files using povray and then add into the output zip.")
    parser.add_argument("--keep-pov", default=False, action='store_true', help='Store compressed pov files into zip')
    parser.add_argument("--keep-rst", default=False, action='store_true', help='Store compressed rst files into zip')
    parser.add_argument("--keep-dat", default=False, action='store_true', help='Store compressed dat files into zip')
    parser.add_argument("--preserve-working", default=False, action='store_true', help='Dont delete the working directory when the run finishes. This only works if a directory is specified using --working-dir')


    args=parser.parse_args()

    dpd_path=Path(args.dpd_path)
    if dpd_path.exists():
        dpd_path=dpd_path.absolute()
    else:
        p = shutil.which(dpd_path)
        if p is None:
            sys.stderr.write(f"dpd-path of '{dpd_path}' doesn't appear to exist as a file, and doesn't resolve use PATH lookup\n")
            sys.exit(1)
        dpd_path=Path(p).absolute()

    (dataset,dataset_dir)=command_line_dataset_open_helper(args.dataset_dir_or_dmpci_template, args.default_dataset_root)

    with ExitStack() as stack:
        if args.working_dir is None:
            if args.preserve_working:
                sys.stderr.write(f"To enable --retain-working an explicit temporary directory must be passed with --working-dir\n")
                sys.exit(1)
            working_dir = Path(stack.enter_context(tempfile.TemporaryDirectory()))
        else:
            working_dir=Path(args.working_dir)
            working_dir.mkdir(parents=True, exist_ok=True)
        sys.stderr.write(f"Working dir = {working_dir}\n")

        config=RunConfig(dataset.template, dpd_path, working_dir, dataset.dir)
        config.render_povray=args.render_povray
        config.keep_dat=args.keep_dat
        config.keep_pov=args.keep_pov
        config.keep_rst=args.keep_rst
        config.preserve_working=args.preserve_working
        config.tags=args.tags.replace(",",";") # Comma seperated on command line, but semi-colon separated internally

        dataset.template.print_parameters()

        #for x in con.get_pivottable():
        #    print(x)

        if args.num_processes=="max":
            processes=os.cpu_count()
        elif args.num_processes=="halfmax":
            processes=int(os.cpu_count()/2)
        else:
            processes=int(args.num_processes)
        processes=max(1, processes)

        if processes > 1:
            with multiprocessing.Pool(processes=processes) as pool:
                done=0
                for _ in pool.imap_unordered(run_one,  [config for i in range(0,args.repeats)]):
                    done+=1
                    if (done%10)==0:
                        sys.stderr.write(f"Done {done} of {args.repeats}\n")
        else:
            for i in range(args.repeats):
                run_one(config)
