from typing import *
from dataclasses import dataclass
import random
import re
from pathlib import Path
from collections import OrderedDict

parameter_regex="[a-zA-Z_][a-zA-Z0-9_]+"

@dataclass
class DMPCIParameter:
    name : str
    type : str
    minval : float
    maxval : float

    def generate(self, rng:random.Random) -> Union[float,int]:
        if self.type=="REAL":
            return self.minval + rng.random() * (self.maxval-self.minval)
        elif self.type=="INTEGER":
            return rng.randint(int(self.minval), int(self.maxval))
        else:
            assert False, f"Unknown parameter type {type}"

class DMPCITemplate:
    def __init__(self, src:Path):
        assert src.exists(), "dmpci template file '{src}' does not exist"
        m = re.match("dmpci[.]([^.]+)[.]template", src.name)
        assert m, f"dmpci filename '{src}' is not of the form dmpci.RUNID.template"
        self.run_id=m.group(1)

        with open(src,"r") as file:
            self.body = file.read()

        self.parameters=OrderedDict() # type: Dict[str,DMPCIParameter]
        for l in self.body.splitlines():
            if l.find("EXPLORE-PARAMETER") != -1:
                m=re.match(f"\s*EXPLORE-PARAMETER\s+({parameter_regex})\s+([a-zA-Z]+)\s+([^\s]+)\s+([^\s]+)\s*", l) # type: re.Match
                assert m, f"Line with EXPLORE-PARAMETER can't be parsed : '{l}' "
                param=DMPCIParameter(
                    m.group(1),
                    m.group(2),
                    float(m.group(3)),
                    float(m.group(4))
                )
                assert param.name not in self.parameters
                self.parameters[param.name]=param
        
        for l in self.body.splitlines():
            if l.find("$") != -1:
                m=re.findall("\$\{([^}]+)\}",l)
                assert len(m)>0, f"Line containing $ didn't contain a keyword : '{l}'"
                for key in m:
                    assert key in self.parameters, f"Variable {key} is used, but no parameter called that is known : '{key}'"

    def create_parameters(self, seed=None) -> Dict[str,str]:
        if seed is None:
            seed=random.randint(1, 2**63)

        rng=random.Random(seed)

        res={}
        for p in sorted( self.parameters.values(), key= lambda p: p.name):
            res[p.name] = str(p.generate(rng))
        return res
    
    def substitute_parameters(self, bindings:Dict[str,str]) -> str:
        res=str(self.body)  
        
        assert len(bindings)==len(self.parameters)
        for p in self.parameters.values():
            value=str(bindings[p.name])
            assert p.name in bindings
            vv=f"BIND-PARAMETER {p.name} {value}"
            res = re.sub(f"EXPLORE-PARAMETER\s+{p.name}\s+({parameter_regex})\s+([^\s]+)\s+([^\s]+)", vv, res) 

            pattern=f"${{{p.name}}}"
            res = res.replace(pattern, value, -1)
        return res
     
    def print_parameters(self):
        for p in self.parameters.values():
            print(p)
