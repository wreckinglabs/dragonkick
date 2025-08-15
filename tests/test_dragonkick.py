#
# Copyright (c) 2025 broomd0g <broomd0g@wreckinglabs.org>
#
# This software is released under the MIT License.
# See the LICENSE file for more details.

import os
import shutil
import unittest

from pathlib import Path

from dragonkick.main import main, GetParser, EX_NOINPUT, EX_UNAVAILABLE, EX_CANTCREAT


class TestDragonKickArgs(unittest.TestCase):

    def setUp(self):
        self.parser = GetParser()

    def test_required_arguments(self):
        # Should fail without --project-name
        with self.assertRaises(SystemExit):
            self.parser.parse_args(["./sysroot/bin/ls"])

        # Should fail without a target
        with self.assertRaises(SystemExit):
            self.parser.parse_args(["-n", "my_project"])

    def test_single_target(self):
        args = self.parser.parse_args([
            "-n", "my_project",
            "-o", "/tmp/test_project",
            "./sysroot/bin/ls"
        ])
        self.assertEqual(args.project_name, "my_project")
        self.assertEqual(args.project_dir, Path("/tmp/test_project"))
        self.assertEqual(args.targets, ["./sysroot/bin/ls"])

    def test_multiple_targets(self):
        args = self.parser.parse_args([
            "--project-name", "my_project",
            "--project-dir", "/tmp/test_project",
            "./sysroot/bin/ls", "./sysroot/bin/cp"
        ])
        self.assertEqual(args.project_name, "my_project")
        self.assertEqual(args.project_dir, Path("/tmp/test_project"))
        self.assertEqual(
            args.targets, ["./sysroot/bin/ls", "./sysroot/bin/cp"])

    def test_boolean_flags(self):
        # Test defaults
        args = self.parser.parse_args(["-n", "my_project", "./sysroot/bin/ls"])
        self.assertFalse(args.copy_to_project)
        self.assertFalse(args.do_dependency_analysis)
        self.assertFalse(args.do_target_decompilation)
        self.assertFalse(args.force_import)
        self.assertFalse(args.force_remove)
        self.assertFalse(args.ignore_missing)
        self.assertFalse(args.skip_dependency_import)
        self.assertFalse(args.skip_target_analysis)
        self.assertFalse(args.start_ghidra)
        self.assertFalse(args.verbose)
        self.assertFalse(args.zip_project)

        # Test setting all flags to True
        args = self.parser.parse_args([
            "-n", "my_project", "./sysroot/bin/ls",
            "--skip-dependency-import",
            "--skip-target-analysis",
            "-F",               # force_remove
            "-I",               # ignore_missing
            "-a",               # do_dependency_analysis
            "-c",               # copy_to_project
            "-d",               # do_target_decompilation
            "-f",               # force_import
            "-s",               # start_ghidra
            "-v",               # verbose
            "-z",               # zip_project
        ])
        self.assertTrue(args.copy_to_project)
        self.assertTrue(args.do_dependency_analysis)
        self.assertTrue(args.do_target_decompilation)
        self.assertTrue(args.force_import)
        self.assertTrue(args.force_remove)
        self.assertTrue(args.ignore_missing)
        self.assertTrue(args.skip_dependency_import)
        self.assertTrue(args.skip_target_analysis)
        self.assertTrue(args.start_ghidra)
        self.assertTrue(args.verbose)
        self.assertTrue(args.zip_project)

    def test_path_options(self):
        # Test default sysroot
        args = self.parser.parse_args(
            ["-n", "my_project", "./sysroot/bin/ls",])
        self.assertEqual(args.sysroot, Path("/"))

        # Test custom sysroot and Ghidra path
        args = self.parser.parse_args([
            "-n", "my_project", "/bin/ls",
            "-R", "./sysroot",
            '-G', "/opt/ghidra"
        ])
        self.assertEqual(args.sysroot, Path("./sysroot"))
        self.assertEqual(args.ghidra_install_dir, Path("/opt/ghidra"))


class TestMainFunction(unittest.TestCase):
    def setUp(self):
        os.environ["GHIDRA_INSTALL_DIR"] = "/opt/ghidra"

        self.project_dir = Path("/tmp/test_project")
        self.bin_dir = self.project_dir / "bin"
        self.lib_dir = self.project_dir / "lib"
        self.src_dir = self.project_dir / "src"
        self.project_zip = self.project_dir.parent / "my_project.zip"

        if self.project_dir.exists():
            shutil.rmtree(self.project_dir)

        if self.project_zip.is_file():
            self.project_zip.unlink()

        self.sysroot = Path("./tests/sysroot")

        self.parser = GetParser()

    def test_invalid_ghidra_install_dir(self):
        args = self.parser.parse_args([
            "-G", "/opt/invalid_ghidra",
            "-n", "my_project",
            "-o", str(self.project_dir),
            f"{self.sysroot}/bin/ls"
        ])

        ret_code = main(args)
        self.assertEqual(ret_code, EX_UNAVAILABLE)

    def test_invalid_sysroot(self):
        args = self.parser.parse_args([
            "-R", "/opt/invalid_sysroot",
            "-n", "my_project",
            "-o", str(self.project_dir),
            f"{self.sysroot}/bin/ls"
        ])

        ret_code = main(args)
        self.assertEqual(ret_code, EX_NOINPUT)

    def test_invalid_target(self):
        args = self.parser.parse_args([
            "-n", "my_project",
            "-o", str(self.project_dir),
            f"{self.sysroot}/bin/MISSING"
        ])

        ret_code = main(args)
        self.assertEqual(ret_code, EX_NOINPUT)

    def test_single_target(self):
        args = self.parser.parse_args([
            "-n", "my_project",
            "-o", str(self.project_dir),
            f"{self.sysroot}/bin/ls"
        ])

        ret_code = main(args)
        self.assertEqual(ret_code, 0)

    def test_single_target_path_normalized(self):
        path_to_norm = self.project_dir / ".." / self.project_dir.name

        args = self.parser.parse_args([
            "-n", "my_project",
            "-o", str(path_to_norm),
            f"{self.sysroot}/bin/ls"
        ])

        ret_code = main(args)
        self.assertEqual(ret_code, 0)

        # Should have been normalized back
        self.assertTrue(self.project_dir.is_dir())


    def test_single_target_exists_fail(self):
        (self.project_dir / "my_project").mkdir(parents=True)
        (self.project_dir / "my_project" / "my_project.gpr").touch()

        args = self.parser.parse_args([
            "-n", "my_project",
            "-o", str(self.project_dir),
            f"{self.sysroot}/bin/ls"
        ])

        ret_code = main(args)
        self.assertEqual(ret_code, EX_CANTCREAT)

    def test_single_target_force_import(self):
        # Create the project
        args = self.parser.parse_args([
            "-n", "my_project",
            "-o", str(self.project_dir),
            f"{self.sysroot}/bin/ls"
        ])

        ret_code = main(args)
        self.assertEqual(ret_code, 0)

        # Run again with -f
        args = self.parser.parse_args([
            "-n", "my_project",
            "-o", str(self.project_dir),
            "-f",
            f"{self.sysroot}/bin/ls"
        ])

        ret_code = main(args)
        self.assertEqual(ret_code, 0)

    def test_single_target_force_remove(self):
        # Create the project
        args = self.parser.parse_args([
            "-n", "my_project",
            "-o", str(self.project_dir),
            f"{self.sysroot}/bin/ls"
        ])

        ret_code = main(args)
        self.assertEqual(ret_code, 0)

        # Run again with -F
        args = self.parser.parse_args([
            "-n", "my_project",
            "-o", str(self.project_dir),
            "-F",
            f"{self.sysroot}/bin/ls"
        ])

        ret_code = main(args)
        self.assertEqual(ret_code, 0)

    def test_single_target_skip_analysis(self):
        args = self.parser.parse_args([
            "-n", "my_project",
            "-o", str(self.project_dir),
            "--skip-target-analysis",
            f"{self.sysroot}/bin/ls"
        ])

        ret_code = main(args)
        self.assertEqual(ret_code, 0)

    def test_single_target_decompile(self):
        args = self.parser.parse_args([
            "-n", "my_project",
            "-o", str(self.project_dir),
            "-d",
            f"{self.sysroot}/bin/ls"
        ])

        ret_code = main(args)
        self.assertEqual(ret_code, 0)

        # Some decompiled source should be there
        src_dir = self.src_dir / "ls"
        sources = [x for x in src_dir.iterdir() if x.is_file()]
        self.assertGreaterEqual(len(sources), 1)

    def test_single_target_dep_analysis(self):
        args = self.parser.parse_args([
            "-n", "my_project",
            "-o", str(self.project_dir),
            "-a",
            f"{self.sysroot}/bin/ls"
        ])

        ret_code = main(args)
        self.assertEqual(ret_code, 0)

    def test_single_target_zip(self):
        args = self.parser.parse_args([
            "-n", "my_project",
            "-o", str(self.project_dir),
            "-z",
            f"{self.sysroot}/bin/ls"
        ])

        ret_code = main(args)
        self.assertEqual(ret_code, 0)

        self.assertTrue(self.project_zip.is_file())

    def test_single_target_with_sysroot_and_copy(self):
        args = self.parser.parse_args([
            "-R", f"{self.sysroot}",
            "-n", "my_project",
            "-o", str(self.project_dir),
            "-c",
            "/bin/ls"
        ])

        ret_code = main(args)
        self.assertEqual(ret_code, 0)

        bins = [x for x in self.bin_dir.iterdir() if x.is_file()]
        self.assertEqual(len(bins), 1)

        libs = [x for x in self.lib_dir.iterdir() if x.is_file()]
        self.assertEqual(len(libs), 3)

    def test_multiple_targets(self):
        args = self.parser.parse_args([
            "-n", "my_project",
            "-o", str(self.project_dir),
            f"{self.sysroot}/bin/ls", f"{self.sysroot}/bin/cp",
        ])

        ret_code = main(args)
        self.assertEqual(ret_code, 0)

    def test_multiple_targets_glob(self):
        args = self.parser.parse_args([
            "-n", "my_project",
            "-o", str(self.project_dir),
            "-c",
            f"{self.sysroot}/bin/*",
        ])

        ret_code = main(args)
        self.assertEqual(ret_code, 0)

        bins = [x for x in self.bin_dir.iterdir() if x.is_file()]
        self.assertEqual(len(bins), 2)

    def test_multiple_targets_ignore_missing(self):
        args = self.parser.parse_args([
            "-n", "my_project",
            "-o", str(self.project_dir),
            "-cI",
            f"{self.sysroot}/bin/ls", f"{self.sysroot}/bin/cp", f"{self.sysroot}/bin/MISSING",
        ])

        ret_code = main(args)
        self.assertEqual(ret_code, 0)

        bins = [x for x in self.bin_dir.iterdir() if x.is_file()]
        self.assertEqual(len(bins), 2)

    def test_multiple_targets_with_sysroot_and_copy(self):
        args = self.parser.parse_args([
            "-R", f"{self.sysroot}",
            "-n", "my_project",
            "-o", str(self.project_dir),
            "-c",
            "/bin/ls", "/bin/cp"
        ])

        ret_code = main(args)
        self.assertEqual(ret_code, 0)

        bins = [x for x in self.bin_dir.iterdir() if x.is_file()]
        self.assertEqual(len(bins), 2)

        libs = [x for x in self.lib_dir.iterdir() if x.is_file()]
        self.assertEqual(len(libs), 5)

    def test_multiple_targets_with_sysroot_skip_deps(self):
        args = self.parser.parse_args([
            "-R", f"{self.sysroot}",
            "-n", "my_project",
            "-o", str(self.project_dir),
            "-c",
            "--skip-dependency-import",
            "/bin/ls", "/bin/cp"
        ])

        ret_code = main(args)
        self.assertEqual(ret_code, 0)

        bins = [x for x in self.bin_dir.iterdir() if x.is_file()]
        self.assertEqual(len(bins), 2)

        libs = [x for x in self.lib_dir.iterdir() if x.is_file()]
        self.assertEqual(len(libs), 0)

    def test_multiple_targets_with_sysroot_remove_existing_bins(self):
        # Copy two targets
        args = self.parser.parse_args([
            "-R", f"{self.sysroot}",
            "-n", "my_project",
            "-o", str(self.project_dir),
            "-c",
            "/bin/ls", "/bin/cp"
        ])

        ret_code = main(args)
        self.assertEqual(ret_code, 0)

        bins = [x for x in self.bin_dir.iterdir() if x.is_file()]
        self.assertEqual(len(bins), 2)

        libs = [x for x in self.lib_dir.iterdir() if x.is_file()]
        self.assertEqual(len(libs), 5)

        # Remove and then copy a single target this time
        args = self.parser.parse_args([
            "-R", f"{self.sysroot}",
            "-n", "my_project",
            "-o", str(self.project_dir),
            "-crf",
            "/bin/ls"
        ])

        ret_code = main(args)
        self.assertEqual(ret_code, 0)

        bins = [x for x in self.bin_dir.iterdir() if x.is_file()]
        self.assertEqual(len(bins), 1)

        libs = [x for x in self.lib_dir.iterdir() if x.is_file()]
        self.assertEqual(len(libs), 3)

    def test_multiple_targets_with_sysroot_and_many_options(self):
        args = self.parser.parse_args([
            "-R", f"{self.sysroot}",
            "-n", "my_project",
            "-o", str(self.project_dir),
            "-cFfrzadI",
            "--skip-dependency-import",
            "--skip-target-analysis",
            "/bin/ls", "/bin/cp", "/bin/MISSING"
        ])

        ret_code = main(args)
        self.assertEqual(ret_code, 0)

        bins = [x for x in self.bin_dir.iterdir() if x.is_file()]
        self.assertEqual(len(bins), 2)

        # --skip-dependency-import
        libs = [x for x in self.lib_dir.iterdir() if x.is_file()]
        self.assertEqual(len(libs), 0)


if __name__ == "__main__":
    unittest.main()
