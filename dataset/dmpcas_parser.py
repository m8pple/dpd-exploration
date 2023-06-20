import re
from pathlib import Path
from typing import *
import sqlite3
import numpy as np

from .results_bundle import ResultsMatrix
from .dmpci_template import DMPCITemplate, parameter_regex

def parse_dmpcas(template:DMPCITemplate, exp_id:str, src_dir:Path, tags:str="") -> ResultsMatrix:
    
    with open(src_dir / f"dmpci.{exp_id}", "r") as s:
        dmpci=s.read()

    configuration=np.zeros( shape=(len(template.parameters),), dtype=np.float64 )
    for (i,p) in enumerate(template.parameters.values()):
        pattern=f"BIND-PARAMETER\s+{p.name}\s+([^\s]+)"
        m = re.search(pattern, dmpci)
        assert m, f"Couldn't find pattern '{pattern}'"
        configuration[i]= float(m.group(1))

    with open(src_dir / f"dmpcas.{exp_id}", "r") as f:
        lines=f.readlines()

    res={} # type: Dict[int, Dict[str,float]]
    time=None
    time_dict=None
    time_list=[]
    i=0
    while i<len(lines):
        key=lines[i].strip()
        if key=="":
            continue
        
        m=re.match("Time = ([0-9]+)", key)
        if m:
            time=int(m.group(1))
            time_dict={} # type: Dict[str,float]
            res[time]=time_dict
            time_list.append(time)
            i += 1
            continue

        vals1=lines[i+1].split(None)
        if len(vals1)==6:
            # this is a tensor. skip for now
            assert len(lines[i+2].split())==6
            assert len(lines[i+3].split())==6
            assert lines[i+4].strip()==""
            i += 5
            continue

        if lines[i+2].strip()=="":
            # This is a scalar. Ignore the standard deviation
            time_dict[key]=float(vals1[0])
            i+=3
            continue

        # This is a vector 
        assert len(lines[i+2].split())==2, f"At line {i}, line = {lines[i+2]}"
        assert len(lines[i+3].split())==2
        assert len(lines[i+4].split())==2
        assert lines[i+5].strip()==""
        # Just put the vector magnitude in
        vals4=lines[i+4].split()
        time_dict[key]=float(vals4[0])
        i+= 6

    run_id=template.run_id
    times=np.array(time_list, dtype=np.int32)
    parameters=np.array(list(template.parameters.keys()), dtype=object)
    observables=np.array(list(time_dict.keys()), dtype=object)
    
    bundle=ResultsMatrix(run_id, parameters, observables, times)

    data=np.ndarray(shape=(len(times), len(observables)), dtype=np.float64 )
    for tindex in range(0,times.shape[0]):
        os=res[times[tindex]]
        assert np.all( observables==np.array(list(os.keys()), dtype=object) ), f"ref={observables}, got={os.keys()}"
        data[tindex,:]=np.array(list(os.values()))

    bundle.add_experiment(exp_id, configuration, data, tags)

    return bundle
