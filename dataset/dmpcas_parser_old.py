import re
from pathlib import Path
from typing import *
import sqlite3

def parse_dmpcas(src:Path) -> Dict[int, Dict[str,float]]:
    with open(str(src), "r") as f:
        lines=f.readlines()

    res={} # type: Dict[int, Dict[str,float]]
    time=None
    time_dict=None
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

    return res

class ResultsDB:
    def __init__(self, db:Path):    
        con=sqlite3.connect(str(db))
        self.con=con # type: sqlite3.Connection
        
        cur=con.cursor()

        cur.execute("CREATE TABLE IF NOT EXISTS experiments(id INTEGER PRIMARY KEY, name TEXT UNIQUE)")
        cur.execute("CREATE TABLE IF NOT EXISTS observables(id INTEGER PRIMARY KEY, name TEXT UNIQUE)")
        cur.execute("CREATE TABLE IF NOT EXISTS parameters(id INTEGER PRIMARY KEY, name TEXT UNIQUE)")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS configuration(
                experiment_id INTEGER,
                parameter_id INTEGER,
                value REAL
            )""")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS results(
                experiment_id INTEGER,
                observable_id INTEGER,
                time INTEGER,
                value REAL
            )""")
        
        self.experiment_ids={}
        for (id,name) in cur.execute("SELECT id,name FROM experiments"):
            self.experiment_ids[name]=id
        
        self.parameter_ids={}
        for (id,name) in cur.execute("SELECT id,name FROM parameters"):
            self.parameter_ids[name]=id

        self.observable_ids={}
        for (id,name) in cur.execute("SELECT id,name FROM observables"):
            self.observable_ids[name]=id

    def __del__(self):
        if self.con:
            self.con.close()
        self.con=None

    def get_param_id(self, name):
        id=self.parameter_ids.get(name, None)
        if id:
            return id
        
        cur=self.con.cursor()
        with self.con:
            cur.execute("SELECT id FROM parameters WHERE name=?", (name,))
            res=cur.fetchone()
            if res is None:
                cur.execute("INSERT INTO parameters(name) VALUES(?)", (name,))
                cur.execute("SELECT id FROM parameters WHERE name=?", (name,))
                res=cur.fetchone()
            id=res[0]
            
        self.parameter_ids[name]=id
        return id
    
    def get_observable_id(self, name):
        id=self.observable_ids.get(name, None)
        if id:
            return id
        
        cur=self.con.cursor()
        with self.con:
            cur.execute("SELECT id FROM observables WHERE name=?", (name,))
            res=cur.fetchone()
            if res is None:
                cur.execute("INSERT INTO observables(name) VALUES(?)", (name,))
                cur.execute("SELECT id FROM observables WHERE name=?", (name,))
                res=cur.fetchone()
                assert res is not None
            id=res[0]
            
        self.observable_ids[name]=id
        return id


    def add_experiment(self, name:str, params:Dict[str,float], results:Dict[int,Dict[str,float]]):
        if name in self.experiment_ids:
            return

        con=self.con
        cur=con.cursor()
        with con:
            cur.execute("INSERT INTO experiments(name) VALUES(?)", (name,))
            cur.execute("SELECT id FROM experiments WHERE name=?", (name,))
            exp_id=cur.fetchone()[0]
            self.experiment_ids[name] = exp_id

            for (k,v) in params.items():
                param_id=self.get_param_id(k)
                cur.execute("INSERT INTO configuration(experiment_id,parameter_id,value) VALUES (?,?,?)", (exp_id, param_id, v))

            tuples=[]
            for (t,vals) in results.items():
                for (k,v) in vals.items():
                    tuples.append( (self.get_observable_id(k), t, v) )

            cur.executemany(f"INSERT INTO results(experiment_id,observable_id,time,value) VALUES ({exp_id},?,?,?)", tuples)

    # TODO: This is far slower than it could be, as we could use sqlite specific optimisaitons
    # to do it, e.g. attaching one database then doing an insert.
    # This entire design is a bit silly - if we just had stable observables and parameters
    # there would be no issues
    def merge_from(self, other:"ResultsDB"):
        here_cur=self.con.cursor()
        other_cur=other.con.cursor()
        with self.con:
            known_experiments=set(self.experiment_ids.keys())
            other_experiments=set(other.experiment_ids.keys())
            new_experiments=other_experiments - new_experiments
            if len(new_experiments)==0:
                return
            
            param_id_map={}
            for (id,name) in other_cur.execute("SELECT (id,name) FROM parameters").fetchall():
                param_id_map[self.get_param_id(name)] = id

            observable_id_map={}
            for (id,name) in other_cur.execute("SELECT (id,name) FROM observable").fetchall():
                observable_id_map[self.get_observable_id(name)] = id

            param_id_map={}
            for (id,name) in other_cur.execute("SELECT (id,name) FROM parameters").fetchall():
                param_id_map[self.get_param_id(name)] = id

            other_rows = other_cur.execute("SELECT (experiment_id,parameter_id,value) FROM configuration")
            new_rows = [ x for x in other_rows if (x[0] in new_experiments)]
            here_cur.executemany("INSERT (experiment_id,parameter_id,value) INTO configuration VALUES (?,?,?)", new_rows)

            other_rows = other_cur.execute("SELECT (experiment_id,observable_id,time,value) FROM experiments").fetchall()
            new_rows = [ x for x in other_rows if (x[0] in new_experiments) ]
            here_cur.executemany("INSERT (experiment_id,observable_id,time,value) INTO experiments VALUES (?,?,?,?)", new_rows)
            