import re
from pathlib import Path
from typing import *
import sqlite3
import h5py
import numpy as np
import os
import zipfile
import io
import sys
import tempfile
import math

from .dmpci_template import DMPCITemplate, DMPCIParameter

def _is_vector_of(x, dtype):
    return len(x.shape)==1 and x.dtype==dtype


class ResultsMatrix:
    """
    The result of one experiment is a 2d nTimes * nObservables matrix
    A bundle of experiments is a 3d nExperiments * nTimes * nObservables matrix
    """

    def _ensure_experiment_space(self, n:int):
        if self.nExperiments+n > self.experiment_capacity:
            new_capacity=max( self.nExperiments+10, self.nExperiments+n, int(self.experiment_capacity*3/2) )
            self.experiments.resize( (new_capacity,) )
            self.tags.resize( (new_capacity,) )
            self.configurations.resize( (new_capacity,self.nParameters) )
            self.data.resize( (new_capacity,self.nTimes,self.nObservables) )
            self.experiment_capacity=new_capacity

    def __init__(self, run_id:str, parameters:np.ndarray, observables:np.ndarray, times:np.ndarray, reserve_exp:int=10):
        assert _is_vector_of(parameters,object), parameters
        assert _is_vector_of(observables,object), observables
        assert _is_vector_of(times,np.int32), times


        self.run_id=run_id
        self.nObservables = observables.shape[0]
        self.nTimes=times.shape[0]
        self.nParameters=parameters.shape[0]

        self.parameters=parameters.copy()
        self.parameters_to_index={ str(k):i[0] for (i,k) in np.ndenumerate(self.parameters)  }
        
        self.observables=observables.copy()
        self.observables_to_index={ str(k):i[0] for (i,k) in np.ndenumerate(self.observables)  }
        
        self.times=times.copy()
        self.times_to_index={ int(k):i[0] for (i,k) in np.ndenumerate(self.times)  }
        
        self.experiment_capacity=reserve_exp
        self.nExperiments=0
        self.experiments=np.array( [""]*self.experiment_capacity, dtype=object )
        self.experiments_index={  } # type: Dict[str,int]
        self.tags=np.array( [""]*self.experiment_capacity, dtype=object)
        self.tags_to_indices={} # type: Dict[str,List[int]]
        
        self.configurations=np.zeros( shape=(self.experiment_capacity, self.nParameters), dtype=np.float64 )
        self.data=np.zeros( shape=(self.experiment_capacity, self.nTimes, self.nObservables), dtype=np.float64 )

    def __contains__(self, experiment_name:str) -> bool:
        return experiment_name in self.experiments_index    

    def add_experiment(self, exp_id:str, configuration:np.ndarray, data:np.ndarray, tags:Optional[str]=None) -> bool:
        assert data.shape == (self.nTimes,self.nObservables)
        assert configuration.shape==(self.nParameters,)

        if exp_id in self.experiments_index:
            return False
        
        tags = tags or ""
        
        self._ensure_experiment_space(1)
        assert self.nExperiments < self.experiment_capacity

        idx=self.nExperiments
        self.experiments[idx]=exp_id
        self.tags[idx]=tags
        self.configurations[idx,:]=configuration
        self.data[idx,:,:]=data
        self.experiments_index[exp_id]=idx

        for tag in tags.split(";"):
            if tag !="" :
                self.tags_to_indices.setdefault(tag, []).append(idx)

        self.nExperiments += 1
        return True
    
    def add_experiments(self, experiments:np.ndarray, configurations:np.ndarray, data:np.ndarray, tags:Optional[np.ndarray]=None):
        assert _is_vector_of(experiments, object)
        n=experiments.shape[0]
        
        src_indices=[ i for (i,v) in enumerate(experiments) if v not in self.experiments_index ]
        nTodo = len(src_indices)
        
        self._ensure_experiment_space(nTodo)
        assert self.nExperiments+nTodo <= self.experiment_capacity

        dest_indices=range(self.nExperiments,self.nExperiments+nTodo)

        self.experiments[dest_indices]=experiments[src_indices]
        if tags is None:
            self.tags[dest_indices]=[""]*len(dest_indices)
        else:
            self.tags[dest_indices]=tags[src_indices]
        self.configurations[dest_indices,:]=configurations[src_indices,:]
        self.data[dest_indices,:,:]=data[src_indices,:,:]
        
        if tags is not None:
            for dst in dest_indices:
                src=src_indices[dst-self.nExperiments]
                for tag in tags[src].split(";"):
                    if tag != "":
                        self.tags_to_indices.setdefault(tag, []).append(dst)
    
        for i in dest_indices:
            self.experiments_index[self.experiments[i]]=i

        self.nExperiments += nTodo

        return nTodo


    def add_bundle(self, other:"ResultsMatrix") -> int:
        assert np.all(self.parameters==other.parameters)
        assert np.all(self.times==other.times)
        assert np.all(self.observables==other.observables)

        return self.add_experiments(other.experiments[0:other.nExperiments], other.configurations[0:other.nExperiments,:], other.data[0:other.nExperiments,:,:], other.tags[0:other.nExperiments])

    def save(self, h5_path:Union[str,io.FileIO]):
        with h5py.File(h5_path, mode='w') as dst:
            dst.attrs["run_id"]=self.run_id
            dst["parameters"]=self.parameters
            dst["observables"]=self.observables
            dst["times"]=self.times
            dst["experiments"]=self.experiments[0:self.nExperiments]
            print(self.tags)
            dst["tags"]=self.tags[0:self.nExperiments]
            dst["configurations"]=self.configurations[0:self.nExperiments,:]
            dst["data"]=self.data[0:self.nExperiments,:,:]

    @staticmethod
    def load(h5_path:str):
        with h5py.File(h5_path, mode="r") as src:
            run_id=src.attrs["run_id"]
            parameters=np.array(src["parameters"].asstr(), dtype=object)
            observables=np.array(src["observables"].asstr(), dtype=object)
            times=np.array(src["times"], dtype=np.int32)
            experiments=np.array(src["experiments"].asstr(), dtype=object)
            tags=np.array(src["tags"].asstr(), dtype=object)
            configurations=np.array(src["configurations"], dtype=np.float64)
            data=np.array(src["data"], dtype=np.float64)
            
            res=ResultsMatrix(run_id, parameters, observables, times, reserve_exp=experiments.shape[0])
            res.add_experiments(experiments, configurations, data, tags)
            return res
        
    def load_from_zip(src:Union[Path,zipfile.ZipFile], internal_path:str):
        if not isinstance(src,zipfile.ZipFile):
            with zipfile.ZipFile(src) as zsrc:
                return ResultsMatrix.load_from_zip(zsrc, internal_path)
        assert isinstance(src,zipfile.ZipFile)
        zsrc=cast(zipfile.ZipFile, src)

        bytes=zsrc.read(internal_path)
        return ResultsMatrix.load( io.BytesIO(bytes) )


class Dataset:
    def merge_run_bundles(self) -> int:
        added=0
        for p in self.dir.glob("sample_*.zip"):
            v = p.name.removesuffix(".zip")
            if self.matrix and v in self.matrix:
                continue

            vb = ResultsMatrix.load_from_zip(p, f"{v}/{v}.hdf5")
            if self.matrix == None:
                self.matrix = vb
                self.matrix_dirty_count=vb.nExperiments
            else:
                done = self.matrix.add_bundle(vb)
                self.matrix_dirty_count += done
                added += done
        return added

    def flush(self):
        if self.matrix_dirty_count>0:
            ww=tempfile.NamedTemporaryFile(delete=False)
            self.matrix.save(ww)
            os.replace( ww.name,  self.dir / f"{self.id}.hdf5" )
            self.matrix_dirty_count=0

    @staticmethod
    def init_or_open_dataset_from_template( template:DMPCITemplate, dataset_directory:Path ) -> "Dataset":
        """
        Opens a dataset directory, initialising from a dmpci template if needed.
        """

        os.makedirs(dataset_directory, exist_ok=True)
        
        dir = dataset_directory
        name_file = dir / "dataset_id.txt"
        template_file = dir / f"dmpci.{template.run_id}.template"
        
        if name_file.exists() or template_file.exists():
            assert name_file.read_text().strip() == template.run_id, f"File '{name_file}' contains '{name_file.read_text().strip()}', but expected '{template.run_id}'. Given template doesn't match dataset."
            assert template_file.read_text() == template.body, f"File '{template_file}' does not match the template given to init_or_open_dataset_from_template"
        else:
            name_file.write_text(template.run_id)
            template_file.write_text(template.body)

        return Dataset(dataset_directory)


    def __init__(self,  dataset_directory:Path):
        """
        Opens an existing data-set directory.
        """
        self.dir=dataset_directory
        assert self.dir.exists(), f"Path {self.dir} does not exist"
        assert self.dir.is_dir(), f"Path {self.dir} is not a directory"
        
        name_file = self.dir / "dataset_id.txt"
        assert name_file.is_file(), f"File {name_file} does not exist. Is {self.dir} a dataset directory?"
        with open(name_file, "rt") as src:
            self.id = src.read().strip()
        assert re.match("^[a-zA-Z0-9_-]+$", self.id), f"File {name_file} does not contain a valid dataset id"

        template_file = self.dir / f"dmpci.{self.id}.template"
        assert template_file.is_file(), f"DMPCI template file {template_file} does not exist in dataset dir."
        
        self.template = DMPCITemplate(template_file)
        assert self.template.run_id == self.id

        self.parameter_names = [p.name for p in self.template.parameters.values()]

        self.matrix = None # type: Optional[ResultsMatrix]
        self.matrix_dirty_count=0
        
        hdf5_path = self.dir / f"{self.id}.hdf5"
        if hdf5_path.is_file():
            self.matrix = ResultsMatrix.load(hdf5_path)
            assert self.matrix.run_id==self.id
        
        self.merge_run_bundles()

    def get_parameter(self, name_or_index:Union[str,int] ) -> DMPCIParameter:
        if isinstance(name_or_index,str):
            return self.template.parameters[name_or_index]
        else:
            return self.get_parameter(self.parameter_names[name_or_index])

    def export_pivot_csv(self, dst:IO):
        matrix=self.matrix


        parameter_quantiles=None
        if matrix.nExperiments>=10:
            num_quantiles=math.ceil(math.sqrt(matrix.nExperiments))
            parameter_quantiles=np.zeros(shape=(matrix.nExperiments,matrix.nParameters))
            boundaries=np.linspace(0,1,num_quantiles,endpoint=True)
            print(f"{boundaries}", file=sys.stderr)
            for (i,param) in enumerate(self.template.parameters.values()):
                #print(f"{param.name}", file=sys.stderr)
                vv=matrix.configurations[0:matrix.nExperiments,i]
                vv=np.sort(vv)
                #print(f"{vv}", file=sys.stderr)
                qboundaries=np.quantile(vv, boundaries)
                #print(f"{qboundaries}", file=sys.stderr)
                parameter_quantiles[:,i]=np.digitize(matrix.configurations[0:matrix.nExperiments,i], qboundaries)
                #print(f"{parameter_quantiles[:,i]}", file=sys.stderr)
        
        print(f"Sample", file=dst, end="")
        for i in range(matrix.nParameters):
            name=str(matrix.parameters[i])
            print(f",{name}", file=dst, end="")
            if parameter_quantiles is not None:
                print(f",{name}-Q{num_quantiles}Index", file=dst, end="")
                #print(f",{name}-Q{num_quantiles}Centre", file=dst, end="")
        print(",Time,Observable,Value", file=dst)

        for ei in range(matrix.nExperiments):
            prefix=str(matrix.experiments[ei])
            for i in range(matrix.nParameters):
                v=float(matrix.configurations[ei,i])
                prefix+=","+str(v)
                if parameter_quantiles is not None:
                    prefix+=","+str(parameter_quantiles[ei,i])
            for (tindex,tval) in np.ndenumerate(matrix.times):
                for (oi,oname) in np.ndenumerate(matrix.observables):
                    print(f"{prefix}, {tval}, {oname}, {float(matrix.data[ei,tindex,oi])}", file=dst )
        

def command_line_dataset_open_helper(dataset_dir_or_dmpci_template:str, default_dataset_root:str) -> Tuple[Dataset,Path]:
    dataset_dir_or_dmpci_template = Path(dataset_dir_or_dmpci_template)
    if dataset_dir_or_dmpci_template.is_file():
        default_dataset_root=Path(default_dataset_root)
        sys.stderr.write(f"Input {dataset_dir_or_dmpci_template} is a file. Treating as a dmpci template and initing or loading dataset at '{default_dataset_root}'\n")
        template=DMPCITemplate(dataset_dir_or_dmpci_template)
        dataset_dir=default_dataset_root / template.run_id
        sys.stderr.write(f"Template run is called {template.run_id}, initing or loading at dataset directory {dataset_dir}\n")
        dataset=Dataset.init_or_open_dataset_from_template(template, dataset_dir)
    else:
        sys.stderr.write(f"Input {dataset_dir_or_dmpci_template} is a directory, treating as a dataset.\n")
        dataset_dir=dataset_dir_or_dmpci_template
        dataset=Dataset(dataset_dir)    
    return (dataset,dataset_dir)


def merge_run_bundles(dir:Path, run_id:str):
    merged_path = dir / f"{run_id}.hdf5"
    if merged_path.exists():
        acc = ResultsMatrix.load(merged_path)
    else:
        acc = None

    added=0
    for p in dir.glob("sample_*.zip"):
        v = p.name.removesuffix(".zip")
        if v in acc:
            continue

        vb = ResultsMatrix.load_from_zip(p, f"{v}/{v}.hdf5")
        if acc == None:
            acc= vb 
        else:
            done=acc.add_bundle(vb)
            if done>0:
                sys.stderr.write(f"Added {done} from {p}\n")
    
    sys.stderr.write(f"Bundle contains {acc.nExperiments} experiments\n")
    
    acc.save(merged_path)

