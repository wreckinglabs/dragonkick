#
# Copyright (c) 2025 broomd0g <broomd0g@wreckinglabs.org>
#
# This software is released under the MIT License.
# See the LICENSE file for more details.

"""
A simple colorful tool to kickstart Ghidra projects from the command line.
"""

import argparse
import cle
import git
import glob
import io
import os
import pyghidra
import shutil
import subprocess
import sys
import zipfile

from contextlib import contextmanager
from importlib.metadata import metadata
from pathlib import Path
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, TextColumn, BarColumn, SpinnerColumn, TimeElapsedColumn, MofNCompleteColumn
from rich.status import Status
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from ghidra.ghidra_builtins import *


EX_DATAERR = 65
EX_NOINPUT = 66
EX_UNAVAILABLE = 69
EX_SOFTWARE = 70
EX_CANTCREAT = 73
EX_IOERR = 74


console = Console(file=sys.__stdout__, log_path=False)


def SetupDecompiler(program):
    from ghidra.app.decompiler import DecompInterface

    decomp = DecompInterface()
    decomp.openProgram(program)

    return decomp


def DecompileFunction(function, decompiler, timeout: int = 0, monitor=None) -> List:
    from ghidra.util.task import ConsoleTaskMonitor

    if monitor is None:
        monitor = ConsoleTaskMonitor()

    result = decompiler.decompileFunction(function, timeout, monitor)

    if "" == result.getErrorMessage():
        code = result.decompiledFunction.getC()
        signature = result.decompiledFunction.getSignature()
    else:
        code = result.getErrorMessage()
        signature = None

    return [function, signature, code, f"{function.getEntryPoint()}.c", f"{function.getEntryPoint()}::{function}.c"]


def SetFunctionComment(function, comment, listing):
    from ghidra.program.model.listing import CodeUnit

    listing.setComment(function.getEntryPoint(),
                       CodeUnit.PLATE_COMMENT, comment)


def ZipProject(project_dir: Path, project_name: str) -> Path:
    if not project_dir.is_dir():
        raise ValueError(f"'{project_dir}' is not a valid project directory.")

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
    )
    progress_panel = Panel(progress)
    live_group = Group(progress_panel)

    with Live(live_group, refresh_per_second=10) as live:
        project_zip = project_dir.parent / f"{project_name}.zip"

        with zipfile.ZipFile(project_zip, "w", zipfile.ZIP_DEFLATED) as zipf:
            project_files = [x for x in project_dir.rglob("*")]
            task = progress.add_task(
                "[green]Zipping project directory...", total=len(project_files))
            for file in project_files:
                arcname = file.relative_to(project_dir)
                zipf.write(file, arcname)
                progress.update(
                    task, description=f"[green]Added {file.name} to {project_zip.name}")
                progress.update(task, advance=1)

        progress.update(
            task, description="[green]Project zipped")
        progress.stop()
        live.refresh()

    return project_zip.resolve()


def ResolveWithRoot(path_to_resolve: Path, sysroot: Path) -> Path:
    current_path = Path(path_to_resolve)
    # A limit to prevent infinite loops from circular symlinks
    for _ in range(100):
        if not current_path.is_symlink():
            # Not a symlink, we've found our final path
            return current_path

        # It's a symlink, read its destination
        link_destination = current_path.readlink()

        if link_destination.is_absolute():
            # Absolute link: The path is relative to the sysroot
            # e.g., link points to '/usr/bin/real', we want sysroot / 'usr/bin/real'
            next_path = sysroot / link_destination.relative_to(os.path.sep)
        else:
            # Relative link: The path is relative to the symlink's parent directory
            # e.g., link is in '.../sbin/' and points to '../bin/real'
            next_path = current_path.parent / link_destination

        # Normalize the path (e.g., collapse '..' components)
        current_path = Path(os.path.normpath(next_path))

    raise RecursionError(
        "Too many symlink levels; circular symlink suspected.")


def GetParser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )

    pkg_meta = metadata("dragonkick")
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"dragonkick v{pkg_meta['Version']} by {pkg_meta['Author']} <{pkg_meta['Author-email']}>",
        help="show version information",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        default=False,
        help="print verbose information messages",
    )

    parser.add_argument("targets", nargs="+")

    project_group = parser.add_argument_group("Project options")

    project_group.add_argument(
        "-c",
        "--copy-to-project",
        action="store_true",
        default=False,
        help="copy original targets/dependencies into the project tree",
    )

    project_group.add_argument(
        "-F",
        "--force-remove",
        action="store_true",
        default=False,
        help="remove the existing project before proceeding",
    )

    project_group.add_argument(
        "-f",
        "--force-import",
        action="store_true",
        default=False,
        help="force re-import when the project already exists",
    )

    project_group.add_argument(
        "-n",
        "--project-name",
        required=True,
        help="Ghidra project name",
    )

    project_group.add_argument(
        "-o",
        "--project-dir",
        type=Path,
        help="project output directory",
    )

    project_group.add_argument(
        "-r",
        "--remove-existing-binaries",
        action="store_true",
        default=False,
        help="remove the previously copied targets/dependencies from the project tree",
    )

    project_group.add_argument(
        "-s",
        "--start-ghidra",
        action="store_true",
        default=False,
        help="open project in Ghidra after kickstart",
    )

    project_group.add_argument(
        "-z",
        "--zip-project",
        action="store_true",
        default=False,
        help="create a zip archive of the project tree",
    )

    analysis_group = parser.add_argument_group("Analysis options")

    analysis_group.add_argument(
        "--skip-dependency-import",
        action="store_true",
        default=False,
        help="skip importing shared object dependencies into project",
    )

    analysis_group.add_argument(
        "--skip-target-analysis",
        action="store_true",
        default=False,
        help="skip auto-analyzing the targets",
    )

    analysis_group.add_argument(
        "-a",
        "--do-dependency-analysis",
        action="store_true",
        default=False,
        help="peform shared object dependencies analysis",
    )

    analysis_group.add_argument(
        "-d",
        "--do-target-decompilation",
        action="store_true",
        default=False,
        help="decompile and export functions code under project tree",
    )

    path_group = parser.add_argument_group("Path options")
    path_group.add_argument(
        "-I",
        "--ignore-missing",
        action="store_true",
        default=False,
        help="ignore missing target file",
    )
    path_group.add_argument(
        "-R",
        "--sysroot",
        default=os.path.sep,
        type=Path,
        help="search for all targets/dependencies under SYSROOT",
    )

    path_group.add_argument(
        "-G",
        "--ghidra-install-dir",
        default=None,
        type=Path,
        help="Ghidra installation directory",
    )

    return parser


@contextmanager
def capture_ghidra_output():
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    captured_output = io.StringIO()

    try:
        sys.stdout = captured_output
        sys.stderr = captured_output
        yield
    finally:
        sys.stdout = original_stdout
        sys.stderr = original_stderr

        output = captured_output.getvalue()
        if output:
            console.rule("[bold red]Captured PyGhidra Output[/]")
            console.log(output.strip())
            console.rule()


@contextmanager
def capture_cle_output(verbose=False):
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    captured_output = io.StringIO()

    try:
        sys.stdout = captured_output
        sys.stderr = captured_output
        yield
    finally:
        sys.stdout = original_stdout
        sys.stderr = original_stderr

        output = captured_output.getvalue()
        if output and verbose:
            console.rule("[bold red]Captured cle.Loader Output[/]")
            console.log(output.strip())
            console.rule()


def log_error(message: str):
    console.log(f"[bold red]ERROR:[/] {message}")


def log_warning(message: str):
    console.log(f"[bold yellow]WARNING:[/] {message}")


def main(options=None) -> Optional[int]:
    if options is None:
        parser = GetParser()
        options = parser.parse_args(sys.argv[1:])

    sysroot = Path(os.path.normpath(options.sysroot)).resolve()

    if not sysroot.is_dir():
        log_error(f"Sysroot {sysroot} does not exist")
        return EX_NOINPUT

    targets = set()
    for target in options.targets:
        target = os.path.normpath(target)
        if sysroot == Path(os.path.sep):
            target_path = Path(target).resolve()
        else:
            target_path = sysroot / target.lstrip(".").lstrip(os.path.sep)
        target_ex = glob.glob(str(target_path))
        for ex in target_ex:
            target_path = ResolveWithRoot(ex, sysroot)
            if not target_path.is_file():
                if options.ignore_missing:
                    log_warning(
                        f"Target {target_path} does not exist, skipping")
                    continue
                log_error(f"Target {target_path} does not exist")
                return EX_NOINPUT
            targets.add(target_path)

    project_name = options.project_name

    if options.project_dir is not None:
        project_dir = Path(os.path.normpath(options.project_dir))
    else:
        project_dir = Path(project_name)

    bin_dir = project_dir / "bin"
    lib_dir = project_dir / "lib"
    src_dir = project_dir / "src"

    ghidra_project = project_dir / project_name / \
        f"{project_name}.gpr"

    if project_dir.is_dir() and options.force_remove:
        console.log(
            f"[red]Removing existing project [bold]{project_dir.resolve()}[/bold]")
        shutil.rmtree(project_dir)
    elif options.remove_existing_binaries:
        console.log("[red]Removing existing binaries from project")

        if lib_dir.is_dir():
            for lib in lib_dir.iterdir():
                if lib.is_file():
                    lib.unlink()
                    if options.verbose:
                        console.log(
                            f"Removed previous dependency [bold]{lib.name}[/bold]")

        if bin_dir.is_dir():
            for target in bin_dir.iterdir():
                if target.is_file():
                    target.unlink()
                    if options.verbose:
                        console.log(
                            f"Removed previous target [bold]{target.name}[/bold]")

    if ghidra_project.is_file() and not options.force_import:
        log_error(
            f"Ghidra project {ghidra_project.resolve()} already exists, use '-f' to force re-importing binaries")
        return EX_CANTCREAT

    if options.ghidra_install_dir is not None:
        os.environ["GHIDRA_INSTALL_DIR"] = str(options.ghidra_install_dir)
        ghidra_install_dir = options.ghidra_install_dir
    else:
        ghidra_install_dir = Path(os.environ.get(
            "GHIDRA_INSTALL_DIR", "/opt/ghidra"))
        os.environ["GHIDRA_INSTALL_DIR"] = str(ghidra_install_dir)

    with console.status(f"[bold][green]:dragon: Starting PyGhidra from {ghidra_install_dir} :dragon:") as status:
        with capture_ghidra_output():
            try:
                pyghidra.start()
            except ValueError as e:
                log_error(f"Starting Ghidra from {ghidra_install_dir}")
                log_error(f"{e}")
                return EX_UNAVAILABLE
            except Exception as e:
                log_error(f"Starting Ghidra from {ghidra_install_dir}")
                log_error(f"{e}")
                return EX_SOFTWARE

    if pyghidra.started():
        from ghidra.framework import Application
        console.log("PyGhidra started")
        console.log(
            f"Using Ghidra {Application.getApplicationVersion()} from {ghidra_install_dir}")

        console.log(
            f"Setting up project '{project_name}' in {project_dir.resolve()}")
        project_dir.mkdir(exist_ok=True)
        bin_dir.mkdir(exist_ok=True)
        lib_dir.mkdir(exist_ok=True)
        src_dir.mkdir(exist_ok=True)

        console.log(f"Using sysroot {sysroot}")

        if sysroot == Path(os.path.sep):
            use_system_libs = True
            ld_path = []
        else:
            use_system_libs = False
            ld_path = [
                sysroot,
                sysroot / "lib",
                sysroot / "lib64",
                sysroot / "usr" / "lib",
                sysroot / "usr" / "lib64",
            ]

        if options.copy_to_project:
            console.log("Saving binaries under project tree")

        if options.skip_dependency_import:
            console.log("[yellow]Skipping target dependency import")
        else:
            console.log(
                f"Resolving dependency for targets {options.targets}")

        deps = set()

        for target in list(targets)[:]:
            with capture_cle_output(options.verbose):
                try:
                    ld = cle.Loader(target, auto_load_libs=True,
                                    use_system_libs=use_system_libs, ld_path=ld_path)
                except Exception as e:
                    log_error(f"{e}")
                    targets.remove(target)
                    continue

                for k, obj in ld.shared_objects.items():
                    abs_obj_path = Path(obj.binary).resolve()
                    if abs_obj_path.is_file():
                        if obj.is_main_bin:
                            if options.verbose:
                                console.log(
                                    f"Target {abs_obj_path}: {obj.arch}, {obj.linking}, pic={obj.pic}, execstack={obj.execstack}")
                            if options.copy_to_project:
                                shutil.copy2(abs_obj_path, bin_dir)
                        else:
                            if not options.skip_dependency_import:
                                if options.verbose:
                                    console.log(
                                        f"Resolved [bold]{k}[/bold] to {abs_obj_path}")
                                if options.copy_to_project:
                                    shutil.copy2(abs_obj_path, lib_dir)
                                deps.add(abs_obj_path)

        if not options.skip_dependency_import:
            console.log(
                f"Importing {len(deps)} shared object dependencies")
        console.log(f"Importing {len(targets)} targets")

        if options.skip_target_analysis:
            console.log("[yellow]Skipping target analysis")

        if not targets:
            log_error("No target to import")
            return EX_NOINPUT

        if not options.skip_dependency_import and deps:
            progress = Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                MofNCompleteColumn(),
                TimeElapsedColumn(),
            )
            status = Status("Importing dependencies...")
            live_group = Group(Panel(progress), Panel(status))

            with Live(live_group, refresh_per_second=10) as live:
                task = progress.add_task(
                    "[green]Importing dependencies...", total=len(deps))
                for dep in deps:
                    if options.do_dependency_analysis:
                        status.update(
                            f"[green]:dragon: Analyzing [bold]{dep.name}[/bold] :dragon:")
                    else:
                        status.update(
                            f"[green]Importing [bold]{dep.name}[/bold]")

                    with pyghidra.open_program(dep, analyze=options.do_dependency_analysis, project_location=project_dir, project_name=project_name, nested_project_location=True) as flat_api:
                        program = flat_api.getCurrentProgram()

                        if options.do_dependency_analysis:
                            status.update(
                                f"[green]:dragon: Analysis of [bold]{dep.name}[/bold] complete :dragon:")
                        else:
                            status.update(
                                f"[green]Imported [bold]{dep.name}[/bold], creation_date={program.getCreationDate()}, language_id={program.getLanguageID()}")

                        progress.update(
                            task, description=f"[green]Imported [bold]{dep.name}[/bold]")

                    progress.update(task, advance=1)

                progress.update(
                    task, description="[green]Dependencies import complete")
                progress.stop()
                status.update("[green]All dependencies imported!")
                status.stop()
                live.refresh()

        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
        )
        progress_panel = Panel(progress)

        status = Status("Importing targets...")
        status_panel = Panel(status)

        live_group = Group(progress_panel, status_panel)

        with Live(live_group, refresh_per_second=10) as live:
            task = progress.add_task(
                "[green]Importing targets...", total=len(targets))

            for target in targets:
                if options.skip_target_analysis:
                    analyze_target = False
                    status.update(
                        f"[green]Importing [bold]{target.name}[/bold]")
                else:
                    analyze_target = True
                    status.update(
                        f"[green]:dragon: Analyzing [bold]{target.name}[/bold] :dragon:")

                with pyghidra.open_program(target, analyze=analyze_target, project_location=project_dir, project_name=project_name, nested_project_location=True) as flat_api:
                    program = flat_api.getCurrentProgram()

                    progress.update(
                        task, description=f"[green]Imported [bold]{target.name}[/bold]")

                    if analyze_target:
                        status.update(
                            f"[green]:dragon: Analysis of [bold]{target.name}[/bold] complete :dragon:")
                    else:
                        status.update(
                            f"[green]Imported [bold]{target.name}[/bold], creation_date={program.getCreationDate()}, language_id={program.getLanguageID()}")

                    progress.update(task, advance=1)

                    if options.do_target_decompilation:
                        function_manager = program.getFunctionManager()
                        functions = [
                            x for x in function_manager.getFunctionsNoStubs(True)]

                        decompiler = SetupDecompiler(program)

                        target_src = src_dir / target.name
                        target_src.mkdir(parents=True, exist_ok=True)
                        target_repo = git.Repo.init(target_src)

                        for x in target_src.iterdir():
                            if x.is_symlink():
                                x.unlink()

                        status.stop()
                        decomp_progress = Progress(
                            SpinnerColumn(),
                            TextColumn(
                                "[progress.description]{task.description}"),
                            BarColumn(),
                            MofNCompleteColumn(),
                            TimeElapsedColumn(),
                        )
                        status_panel.renderable = decomp_progress

                        decomp_task = decomp_progress.add_task(
                            "[green]Decompiling functions...", total=len(functions))
                        for f in functions:
                            if not f.isThunk():
                                function, signature, code, filename, symlink = DecompileFunction(
                                    f, decompiler)
                                decomp_progress.update(
                                    decomp_task, description=f"[green]Decompiled [bold]{f.getName()}[/bold]")

                                if signature is not None:
                                    function_src = target_src / filename
                                    with open(function_src, "w") as fh:
                                        fh.write(code)

                                    function_link = target_src / symlink
                                    function_link.symlink_to(filename)
                            else:
                                decomp_progress.update(
                                    decomp_task, description=f"[green]Skipping thunk [bold]{f.getName()}[/bold]")

                            decomp_progress.update(decomp_task, advance=1)

                        decomp_progress.update(
                            decomp_task, description="[green]Decompilation complete")
                        decomp_progress.stop()

                        target_repo.git.add(all=True)
                        target_repo.index.commit("Decompiled source refresh")

                        decompiler.dispose()

                    status_panel.renderable = status

            progress.update(
                task, description="[green]Targets import complete")
            progress.stop()
            status.update("[green]All targets imported!")
            status.stop()
            live.refresh()

        if options.zip_project:
            try:
                console.log(
                    f"Project zip saved {ZipProject(project_dir, project_name)}")
            except Exception as e:
                log_error(f"Failed to zip {project_dir}")
                log_error(f"{e}")

        if ghidra_project.is_file():
            console.log(
                f"The project is ready to be opened with Ghidra {ghidra_project.resolve()}")
        else:
            log_error(f"Ghidra project {ghidra_project} not found")
            return EX_UNAVAILABLE

        if options.start_ghidra:
            subprocess.run([ghidra_install_dir / "ghidraRun",
                           ghidra_project.resolve()])

        return 0


if __name__ == "__main__":
    sys.exit(main())
