WIP WIP WIP

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
import datetime
import io
import random
import math
import zipfile
import tempfile
from typing import *
import numpy as np
import scipy.spatial
from contextlib import ExitStack
from tkinter import *
from tkinter import ttk
from PIL import Image, ImageTk

from dataset import command_line_dataset_open_helper, DMPCIParameter, Dataset
from dataset_extract_snapshot_slice import crop_image_whitespace

@dataclass
class ImagePoint:
    def __init__(self, )

    eid_current : str

    label : Optional[str]

    image : ImageTk  # Image being shown in the label. Used to ensure it is not garbage collected 
    widget : ttk.Label
    textlabel : StringVar


class ImageGrid(ttk.Frame):
    def _load_image(self, eid:str) -> Image:
        with zipfile.ZipFile( dataset.dir / f"{eid}.zip" ) as zip:
            fn = f"dmpccs.{eid}.con.{time}.png"
            image_bytes=zip.read(f"{eid}/{fn}")
            assert len(image_bytes)>0

            image= Image.open( io.BytesIO(image_bytes), formats=("jpeg", "png"))
            image=crop_image_whitespace(image)
            return image

    def __init__(self, parent:ttk.Widget, width:int, height:int, time:int, dataset:Dataset, init:List[str]):
        super().__init__(parent)
        self.width=width
        self.height=height
        self.dataset=dataset

        init=list(init)

        self.points=[] # type: List[ImagePoint]
        self.xy_to_point={} #type: Dict[(int,int),ImagePoint]
        self.eid_to_point={} #type: Dict[str,ImagePoint]
        for y in range(height):
            for x in range(width):
                eid = init.pop( random.randrange(len(init)) )
                eindex = dataset.matrix.experiments_index[eid]
                pt = dataset.matrix.configurations[eindex]
                image = self._load_image(eid)
                image_tk = ImageTk.PhotoImage(image)

                label = ttk.Label(self, image=image_tk)
                label.grid(row=2*y, column=x, sticky="NSEW")
                textlabel=StringVar(self, np.array2string(pt,precision=3,floatmode='fixed'))
                text = ttk.Label(self, textvariable=textlabel)
                text.grid(row=2*y+1, column=x)
                image_point=ImagePoint(
                    eid, pt, datetime.datetime.now(),
                    image_tk, label, textlabel
                )
                self.points.append(image_point)
                self.xy_to_point[(x,y)]=image_point
                self.eid_to_point[eid]=image_point

        for c in range(ncols):
            self.columnconfigure(c, weight=1)
        for r in range(nrows):
            self.rowconfigure(2*r, weight=1)

    def set_point(self, target:ImagePoint, eid:str):
        eindex=dataset.matrix.experiments_index[eid]
        del self.eid_to_point[target.eid_current]
        target.pt_current = dataset.matrix.configurations[eindex]
        target.eid_current=eid
        target.time_set=datetime.datetime.now()
        target.image=ImageTk.PhotoImage(self._load_image(eid))
        target.widget.configure(image=target.image)
        target.textlabel.set(np.array2string(target.pt_current,precision=3,floatmode='fixed'))
        self.eid_to_point[eid]=target

    def set_images(self, vals:List[str]):
        assert len(vals) == len(self.points)
        print(f"vals={sorted(vals)}")
        print(f"new = { set(vals) - set(self.eid_to_point.keys())}")
        now=datetime.datetime.now()
        by_age = sorted(list(self.points),  key = lambda p: p.time_set ) # type: List[ImagePoint]
        for v in vals:
            if v in self.eid_to_point:
                continue
            for i in range(len(by_age)):
                candidate=by_age[i]
                if candidate.eid_current not in vals:
                    by_age.pop(i)
                    self.set_point(candidate, v)
                    break

        for i in range(len(self.points)-1):
            for j in range(i+1,len(self.points)):
                assert(self.points[i].eid_current != self.points[j].eid_current)


if __name__=="__main__":

    parser=argparse.ArgumentParser(
        "dataset_display.py"
    )
    parser.add_argument("dataset_dir_or_dmpci_template")
    parser.add_argument("--default_dataset_root", nargs="?", default="dpd_datasets", help="Default directory to put datasets in.")
    
    args=parser.parse_args()

    (dataset,dataset_dir)=command_line_dataset_open_helper(args.dataset_dir_or_dmpci_template, args.default_dataset_root)

    kd=scipy.spatial.KDTree(dataset.matrix.configurations)

    ncols=3
    nrows=3
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

    time=dataset.matrix.times[-1]
    point=np.array([ (p.minval+p.maxval)/2 for p in dataset.template.parameters.values() ])
    
    pictures=ImageGrid(mainframe, ncols, nrows, time, dataset, select_closest(point))
    pictures.grid(column=1, row=0, sticky="NSEW")

    def update_point():
        items = select_closest(point)
        pictures.set_images(items)                    
    
    def on_slider_changed(value, sv:StringVar, slider:ttk.Scale, param:DMPCIParameter):
        sv.set(f"{float(value):.2f}")
        point[param.index]=float(value)
        update_point()
    
    for (i,p) in enumerate(dataset.template.parameters.values()):
        l=ttk.Label( sliders, text=p.name)
        l.grid( column=0, row=2*i )

        s = ttk.Scale(sliders, orient=HORIZONTAL, length=200, from_=p.minval, to=p.maxval, value=point[i])
        s.grid( column=0,row=2*i+1, columnspan=2 )
        
        sv = StringVar()
        t=ttk.Label(sliders,textvariable=sv)
        t.grid( column=1, row=2*i)

        s.configure(command=lambda value, sv=sv, s=s, p=p, : on_slider_changed(value, sv, s, p))

    root.mainloop()
