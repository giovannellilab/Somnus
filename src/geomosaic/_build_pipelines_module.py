import networkx as nx
from networkx.classes import DiGraph
from collections import deque
import networkx as nx
import subprocess
import os
from geomosaic._utils import GEOMOSAIC_ERROR, GEOMOSAIC_PROMPT
from geomosaic._validator import validator_hmms_folder, validator_completeness_contamination_integer, validator_hmmsearch_output_folder
from geomosaic.custom_tools.argsoap_custom import validator_argsoap_database, validator_argsoap_fastafile, validator_argsoap_mapping, validator_argsoap_outfolder, argsoap_database_structure


def build_pipeline_modules(graph: DiGraph, collected_modules: dict, order: list, additional_input: dict, mstart: str="pre_processing", unit=False, dependencies=False):
    G = graph.copy()
    assert mstart in G.nodes()

    dfs_collection = {}
    for m in G.nodes():
        dfs_collection[m] = list(nx.dfs_preorder_nodes(G, source=m))
    
    # Cleaning the Graph, based on the starting point
    for n in graph.nodes():
        if n not in dfs_collection[mstart]:
            G.remove_node(n)

    # Obtaining all descendants of the working graphs
    modules_descendants = {}
    for m in G.nodes():
        modules_descendants[m] = list(nx.descendants(G, m))

    user_choices = {}
    
    if unit:
        raw_queue = [mstart]
    else:
        raw_queue = list(nx.bfs_tree(G, source=mstart).nodes())

    # Defining order
    queue = deque([elem for elem in order if elem in raw_queue])
    skipped_modules = []

    while queue:
        status = False
        my_module = queue[0]

        module_descr = GEOMOSAIC_PROMPT(f"[{my_module}] - ".upper()) + f"{collected_modules[my_module]['description']}"
        module_choices = {}
        if not dependencies:
            module_choices[0] = {"display": "-- Ignore this module (and all successors) --", "package": ""}
        for indice, raw_package in enumerate(collected_modules[my_module]["choices"].items(), start=1):
            pckg_display, pckg_name = raw_package
            module_choices[indice] = {"display": pckg_display, "package": pckg_name}

        prompt_display = f"\n{module_descr}\n" + "\n".join([f"{integer}) {pck_info['display']}" for integer, pck_info in module_choices.items()])
        while not status:
            print(prompt_display)
            
            raw_input = input()

            status, obj = check_user_input(raw_input, list(module_choices.keys()))
            if not status:
                print(obj)
        
        parse_input = obj
        if parse_input == 0:
            skipped_modules.append(my_module)
            G.remove_node(my_module)
            G.remove_nodes_from(modules_descendants[my_module])
            for desc in modules_descendants[my_module]:
                if desc in queue:
                    queue.remove(desc)
            
            queue.popleft()
            continue
        
        user_choices[my_module] = module_choices[parse_input]["package"]
        queue.popleft()
    
    dependencies = list(G.edges())
    order_writing = [elem for elem in order if elem in user_choices]

    return user_choices, dependencies, G, order_writing, skipped_modules


def ask_additional_parameters(additional_input, order_writing):
    additional_parameters = {}

    for module in order_writing:
        if module in additional_input:
            for adt_param, adt_param_tokens in additional_input[module].items():
                if adt_param in additional_parameters:
                    continue

                flag = False
                while not flag:
                    input_adt_param = get_user_path(adt_param_tokens["description"])

                    if adt_param == "hmm_folder" and not validator_hmms_folder(input_adt_param):
                        print(f"{GEOMOSAIC_ERROR}: Invalid input")
                    elif adt_param == "completness_threshold" and not validator_completeness_contamination_integer(input_adt_param):
                        print(f"{GEOMOSAIC_ERROR}: Invalid input")
                    elif adt_param == "contamination_threshold" and not validator_completeness_contamination_integer(input_adt_param):
                        print(f"{GEOMOSAIC_ERROR}: Invalid input")
                    elif adt_param == "assembly_hmmsearch_output_folder" and not validator_hmmsearch_output_folder(input_adt_param, additional_parameters):
                        print(f"{GEOMOSAIC_ERROR}: Invalid input")
                    elif adt_param == "mags_hmmsearch_output_folder" and not validator_hmmsearch_output_folder(input_adt_param, additional_parameters):
                        print(f"{GEOMOSAIC_ERROR}: Invalid input")
                    else:
                        flag = True
                
                # INSERT PARAM FOR CONFIG FILE
                if adt_param_tokens["type"] in ["integer"]:
                    additional_parameters[adt_param] = int(input_adt_param)
                elif adt_param_tokens["type"] in ["string"]:
                    additional_parameters[adt_param] = str(input_adt_param)
                else:
                    additional_parameters[adt_param] = os.path.abspath(input_adt_param)
    
    return additional_parameters


def ask_custom_db(gmpackages_custom_db, user_choices):
    custom_db_info = {}

    for module, tool in user_choices.items():
        if tool in gmpackages_custom_db:
            if tool == "argsoap_custom":
                print(argsoap_database_structure)
            
            custom_db_info[tool] = {}

            for cdb_param, cdb_param_tokens in gmpackages_custom_db[tool].items():
                flag = False
                while not flag:
                    input_cdb_param = get_user_path(cdb_param_tokens["description"])

                    if cdb_param == "argsoap_custom_protein_fasta" and not validator_argsoap_fastafile(input_cdb_param):
                        print(f"{GEOMOSAIC_ERROR}: Invalid input")
                    elif cdb_param == "argsoap_custom_mapping_file" and not validator_argsoap_mapping(input_cdb_param):
                        print(f"{GEOMOSAIC_ERROR}: Invalid input")
                    elif cdb_param == "argsoap_custom_output_folder" and not validator_argsoap_outfolder(input_cdb_param):
                        print(f"{GEOMOSAIC_ERROR}: Invalid input")
                    elif cdb_param == "argsoap_custom_database_folder" and not validator_argsoap_database(input_cdb_param):
                        print(f"{GEOMOSAIC_ERROR}: Invalid input")
                    else:
                        flag = True
                
                # INSERT PARAM FOR CONFIG FILE
                if cdb_param_tokens["type"] in ["integer"]:
                    custom_db_info[tool][cdb_param] = int(input_cdb_param)
                elif cdb_param_tokens["type"] in ["string"]:
                    custom_db_info[tool][cdb_param] = str(input_cdb_param)
                else: # File or folder
                    custom_db_info[tool][cdb_param] = os.path.abspath(input_cdb_param)
    
    return custom_db_info


def get_user_path(description):
    try:
        raw_path = subprocess.check_output(f'read -e -p "{description}: \n" var; echo $var', shell=True, executable='/bin/bash')
        path = raw_path.rstrip().decode('utf-8')
        return path
    except Exception as e:
        print(description)
        input_adt_param=input()
        return input_adt_param


def import_graph(edges: list) -> DiGraph:
    g = nx.DiGraph()
    for source, target in edges:
        g.add_edge(source, target)
    
    return g


def check_user_input(input, list_ints):
    false_payload = (False, f"{GEOMOSAIC_ERROR}: Invalid input")

    try:
        user_input = int(input)

        if user_input not in list_ints:
            return false_payload
    except:
        return false_payload
    
    return True, user_input
