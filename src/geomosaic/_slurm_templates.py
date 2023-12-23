import os
from subprocess import check_call
from geomosaic._utils import GEOMOSAIC_PROCESS, GEOMOSAIC_ERROR
import yaml


def exectype_slurm(args, geomosaic_samples, geomosaic_dir, gm_snakefile, unit):
    threads = args.threads
    memory = args.memory
    partition = "" if args.partition is None else f"#SBATCH --partition={args.partition}"
    mail_type = "" if args.mail_type is None else f"#SBATCH --mail-type={args.mail_type}"
    mail_user = "" if args.mail_user is None else f"#SBATCH --mail-user={args.mail_user}"
    samples_number = len(geomosaic_samples)
    path_geomosaic_snakefile = gm_snakefile
    output_script = os.path.abspath("slurm_geomosaic.sh") if args.output_script is None else os.path.abspath(args.output_script)
    extdb_output_script = os.path.abspath("slurm_extdb_geomosaic.sh") if args.extdb_output_script is None else os.path.abspath(args.extdb_output_script)
    list_sample_output = os.path.abspath(args.list_sample_output)
    
    if args.folder_logs is not None:
        folder_logs = os.path.abspath(args.folder_logs)

        if not os.path.isdir(folder_logs):
            print(f"{GEOMOSAIC_PROCESS}: Creating the specified folder logs: 'mkdir -p {folder_logs}'")
            check_call(["mkdir", "-p", folder_logs])
        
        slurm_logs = "#SBATCH --output=" +os.path.join(folder_logs, "slurm-%A_%a.out")
    else:
        slurm_logs = ""
    
    update_threads(unit, geomosaic_dir, threads)

    sw = slurm_workflow.format(
        threads = threads, 
        memory = memory, 
        partition = partition, 
        samples_number = samples_number,
        path_geomosaic_snakefile = path_geomosaic_snakefile,
        path_list_sample = list_sample_output,
        mail_type = mail_type,
        mail_user = mail_user,
        slurm_logs = slurm_logs,
    )

    extdb = slurm_extdb.format(
        memory = memory,
        slurm_logs = slurm_logs,
        partition = partition,
        mail_type = mail_type,
        mail_user = mail_user,
        path_extdb_snakefile = str(os.path.join(geomosaic_dir, "Snakefile_extdb.smk"))
    )
    
    return output_script, sw, extdb_output_script, extdb, list_sample_output


def update_threads(unit, geomosaic_wdir, threads):
    filename = "config_unit.yaml" if unit else "config.yaml"
    config_file = os.path.join(geomosaic_wdir, filename)

    # CHECK CONFIG FILE EXISTS
    if not os.path.isfile(config_file):
        print(f"\n{GEOMOSAIC_ERROR}: '{filename}' does not exists in the Geomosaic WDIR: {geomosaic_wdir}")
        exit(1)
    
    # OPEN CONFIG FILE
    with open(config_file) as file:
        configs = yaml.load(file, Loader=yaml.FullLoader)

    # CHECK THREADS VALUE
    if threads != configs["threads"]:
        print(f"{GEOMOSAIC_PROCESS}: Geomosaic will overwite the 'threads' value in the config file since it is idifferent.")

        configs["threads"] = threads
        with open(config_file, 'w') as fd_config:
            yaml.dump(configs, fd_config)


slurm_workflow = """#!/bin/bash

#SBATCH --job-name="Geomosaic"
#SBATCH --time=96:00:00
#SBATCH --cpus-per-task={threads}
#SBATCH --mem={memory}G
#SBATCH --array=1-{samples_number}
{slurm_logs}
{partition}
{mail_type}
{mail_user}

#
# Created with Geomosaic
# 


single_sample="$(tail -n +$SLURM_ARRAY_TASK_ID {path_list_sample} | head -n1)"


snakemake --use-conda --cores {threads} --config SAMPLES=$single_sample -s {path_geomosaic_snakefile}
"""

slurm_extdb = """#!/bin/bash

#SBATCH --job-name="Extdb_GM"
#SBATCH --time=96:00:00
#SBATCH --cpus-per-task=7
#SBATCH --mem={memory}G
{slurm_logs}
{partition}
{mail_type}
{mail_user}

#
# Created with Geomosaic
# 


snakemake --use-conda --cores 7 -s {path_extdb_snakefile}
"""
