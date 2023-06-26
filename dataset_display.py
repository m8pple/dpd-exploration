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
import io
import zipfile
import tempfile
from typing import *
import numpy as np
import scipy.spatial
from contextlib import ExitStack
from tkinter import *
from tkinter import ttk
from PIL import Image, ImageTk

from dataset import command_line_dataset_open_helper, DMPCIParameter




if __name__=="__main__":

    parser=argparse.ArgumentParser(
        "dataset_display.py"
    )
    parser.add_argument("dataset_dir_or_dmpci_template")
    parser.add_argument("--default_dataset_root", nargs="?", default="dpd_datasets", help="Default directory to put datasets in.")
    
    args=parser.parse_args()

    (dataset,dataset_dir)=command_line_dataset_open_helper(args.dataset_dir_or_dmpci_template, args.default_dataset_root)

    kd=scipy.spatial.KDTree(dataset.matrix.configurations)

    ncols=5
    nrows=5
    pwidth=128
    pheight=128

    def select_closest(p : np.ndarray) -> List[str]:
        print(p)
        (_,indices) = kd.query(p, k=ncols*nrows)
        print(indices)
        eid=list(dataset.matrix.experiments[indices])
        return eid


    root = Tk()
    root.title(f"DPD Exploration - {dataset.id}")
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)

    mainframe = ttk.Frame(root, padding="3 3 12 12")
    mainframe.grid(column=0, row=0, sticky=(N, W, S,E))
    mainframe.columnconfigure(1, weight=1)
    mainframe.rowconfigure(0, weight=1)

    sliders=ttk.Frame(mainframe)
    sliders.grid(column=0, row=0, sticky="NSEW")

    xy_to_labels={} # type: Dict[Tuple(int,int),ttk.Label]
    
    pictures=ttk.Frame(mainframe)
    pictures.grid(column=1, row=0, sticky="NSEW")
    for c in range(ncols):
        pictures.columnconfigure(c, weight=1)
    for r in range(nrows):
        pictures.rowconfigure(r, weight=1)

    blank=Image.new("RGB", (pwidth,pheight))
    tkblank=ImageTk.PhotoImage(blank)
    for y in range(nrows):
        for x in range(ncols):
            pxy=ttk.Label(pictures, image=tkblank)
            pxy.grid(column=x, row=y)
            xy_to_labels[(x,y)] = pxy

    point=np.array([ (p.minval+p.maxval)/2 for p in dataset.template.parameters.values() ])
    
    time=dataset.matrix.times[-1]

    def update_point():
        items = select_closest(point)
        for y in range(nrows):
            for x in range(ncols):
                linear=y*ncols+x
                eid = items[linear]

                sys.stderr.write(f"{eid}\n")

                with zipfile.ZipFile( dataset.dir / f"{eid}.zip" ) as zip:
                    fn = f"dmpccs.{eid}.con.{time}.png"
                    image_bytes=zip.read(f"{eid}/{fn}")
                    assert len(image_bytes)>0

                    image=Image.open( io.BytesIO(image_bytes), formats=("jpeg", "png"))

                image=image.resize((pwidth,pheight))

                tkimage=ImageTk.PhotoImage(image)
                tt=xy_to_labels[(x,y)]
                tt.configure(image=tkimage)
                # Need to ensure the image is not garbage collected. Hack to keep a reference.
                tt.dbt_ref=tkimage
                    
    
    def on_slider_changed(value, sv:StringVar, slider:ttk.Scale, param:DMPCIParameter):
        sv.set(f"{float(value):.2f}")
        point[param.index]=float(value)
        update_point()
    
    for (i,p) in enumerate(dataset.template.parameters.values()):
        l=ttk.Label( sliders, text=p.name)
        l.grid( column=0, row=2*i )

        s = ttk.Scale(sliders, orient=HORIZONTAL, length=100, from_=p.minval, to=p.maxval, value=point[i])
        s.grid( column=0,row=2*i+1, columnspan=2 )
        
        sv = StringVar()
        t=ttk.Label(sliders,textvariable=sv)
        t.grid( column=1, row=2*i)

        s.configure(command=lambda value, sv=sv, s=s, p=p, : on_slider_changed(value, sv, s, p))

    root.mainloop()
