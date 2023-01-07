import click
import pathlib
import os
from slurm import submit_slurm_job
from executor import run_command

executables = [{'compile_command': "/opt/apps/alces/intel/psxe/2019u5/impi/2019.5.281/intel64/bin/mpiicc op1.c -o op1 -std=c99",
                'name': "op1", 'args': ['{artifacts_path}/input_64_512_960.dat', '{artifacts_path}/kernel_5.dat', 'op1_out.dat']},
               {'compile_command': "/opt/apps/alces/intel/psxe/2019u5/impi/2019.5.281/intel64/bin/mpiicc op2.c -o op2 -std=c99",
               'name': "op2", 'args': ['{artifacts_path}/a1.dat', '{artifacts_path}/b1.dat', 'op2_out.dat']},
               {'compile_command': "/opt/apps/alces/intel/psxe/2019u5/impi/2019.5.281/intel64/bin/mpiicc op3.c -o op3 -std=c99",
               'name': "op3", 'args': ['{artifacts_path}/sort.dat', 'op3_out.dat']}]


def compile(basedir, artifacts_path):
    successful_compilations = []

    for exe in executables:
        command = exe['compile_command']
        e = exe["name"]
        command = command.format_map({'artifacts_path': artifacts_path})
        output_file_name = "%s_compilation.out" % e
        output_file_path = os.path.join(basedir, output_file_name)
        p = run_command(command, cwd=basedir, output_file=output_file_path)
        rc = p.returncode
        if rc == 0:
            path_to_executable = os.path.join(basedir, e)
            exe["full_path"] = path_to_executable
            successful_compilations.append(exe)
    
    return successful_compilations


def submit_job_for_run(exe, num_par, identifier, artifacts_path, basedir):
    args = [x.format_map({'artifacts_path': artifacts_path}) for x in exe["args"]]
    results_file_name = os.path.join(basedir, "iresults.csv")
    command_to_run = ["python", os.path.join(artifacts_path, "single-instance-runner.py")]
    command_to_run += ["--num-par", str(num_par)]
    command_to_run += ["--identifier", str(identifier)]
    command_to_run += ["--results-file", results_file_name]
    command_to_run += ["--basedir", basedir]
    command_to_run += ["--executable", exe["full_path"]]
    command_to_run += ["--args", ",".join(args)]
    command_to_run += ["--parallel", "MPI"]

    command_to_run = " ".join(command_to_run)
    slurm_template = os.path.join(artifacts_path, "slurm_template.tpl")
    return submit_slurm_job([command_to_run], slurm_template, cwd=basedir,
                            time_limit=60, num_cores=1, num_tasks=num_par)

def submit_cleanup_job(basedir, identifier, artifacts_path, dependencies):
    command_to_run = ["python", os.path.join(artifacts_path, "cleanup-user.py")]
    command_to_run += ["--basedir", basedir]
    command_to_run += ["--identifier", str(identifier)]
    command_to_run += ["--leaderboard-path", artifacts_path]
    command_to_run += ["--iresults", "iresults.csv"]
    print("Scheduling cleanup job...")
    command_to_run = " ".join(command_to_run)
    slurm_template = os.path.join(artifacts_path, "slurm_template.tpl")
    return submit_slurm_job([command_to_run], slurm_template, cwd=basedir,
                            time_limit=60, num_cores=1, dependencies=dependencies)


@click.command()
@click.option('--basedir', default=None, help='Directory to find executables')
@click.option('--identifier', required=True, help='Identify this submission')
@click.option('--artifacts-path', default=None, help='Location of artifacts')
def run(basedir, identifier, artifacts_path):
    if artifacts_path is None:
        artifacts_path = pathlib.Path(__file__).parent.resolve()
    
    basedir = os.path.abspath(basedir)
    
    executables = compile(basedir, artifacts_path)

    max_ranks = 33
    rank_nums = []
    ranknum = 1
    while ranknum < max_ranks:
        rank_nums.append(ranknum)
        ranknum *= 2
    rank_nums = list(reversed(rank_nums))

    job_ids = []
    for e in executables:
        for c in rank_nums:
            job_id = submit_job_for_run(e, c, identifier, artifacts_path, basedir)
            print(job_id)
            job_ids.append(job_id)
    if len(job_ids)>0:
        print(submit_cleanup_job(basedir, identifier, artifacts_path, job_ids))


if __name__=="__main__":
    run()