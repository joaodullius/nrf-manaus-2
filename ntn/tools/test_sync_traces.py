"""O sync deve converter cada .bin novo para traces-txt com nome coerente."""

import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from unittest import mock

import sync_traces

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.normpath(os.path.join(HERE, "..", "02_leo_replay", "data"))
DB = os.path.join(DATA, "trace_db_external_eae22c84-2506-423a-883e-91bd9b2ad229.tar.gz")


def make_bin(directory, name, content=b"initial_trace_timestamp_epoch_us: 1788660933791348\n"):
    path = os.path.join(directory, name)
    with open(path, "wb") as fh:
        fh.write(content)
    return path


class ConvertBinsTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.bin_dir = os.path.join(self.root, "traces-bin")
        self.txt_dir = os.path.join(self.root, "traces-txt")
        os.makedirs(self.bin_dir)
        make_bin(self.bin_dir, "20260906_0226_SIOT1_BRA_YG.bin")
        self.fake = lambda b, d: [
            sync_traces.nrf_trace.TraceRecord(
                timestamp=sync_traces.nrf_trace._UNIX_EPOCH, label="X", text="y"
            )
        ]

    def test_writes_txt_next_to_the_others_keeping_the_base_name(self):
        ok, failed = sync_traces.convert_bins(
            ["20260906_0226_SIOT1_BRA_YG.bin"], self.bin_dir, self.txt_dir,
            "db.tar.gz", convert=self.fake,
        )
        self.assertEqual(ok, ["20260906_0226_SIOT1_BRA_YG.txt"])
        self.assertEqual(failed, [])
        self.assertTrue(os.path.isfile(
            os.path.join(self.txt_dir, "20260906_0226_SIOT1_BRA_YG.txt")))

    def test_skips_when_txt_is_newer_than_bin(self):
        sync_traces.convert_bins(
            ["20260906_0226_SIOT1_BRA_YG.bin"], self.bin_dir, self.txt_dir,
            "db.tar.gz", convert=self.fake,
        )
        ok, failed = sync_traces.convert_bins(
            ["20260906_0226_SIOT1_BRA_YG.bin"], self.bin_dir, self.txt_dir,
            "db.tar.gz", convert=self.fake,
        )
        self.assertEqual(ok, [])

    def test_force_reconverts_an_up_to_date_txt(self):
        sync_traces.convert_bins(
            ["20260906_0226_SIOT1_BRA_YG.bin"], self.bin_dir, self.txt_dir,
            "db.tar.gz", convert=self.fake,
        )
        ok, _ = sync_traces.convert_bins(
            ["20260906_0226_SIOT1_BRA_YG.bin"], self.bin_dir, self.txt_dir,
            "db.tar.gz", convert=self.fake, force=True,
        )
        self.assertEqual(ok, ["20260906_0226_SIOT1_BRA_YG.txt"])

    def test_a_failing_conversion_is_reported_not_raised(self):
        def boom(b, d):
            raise sync_traces.nrf_trace.TraceError("sem trace database")

        ok, failed = sync_traces.convert_bins(
            ["20260906_0226_SIOT1_BRA_YG.bin"], self.bin_dir, self.txt_dir,
            "db.tar.gz", convert=boom,
        )
        self.assertEqual(ok, [])
        self.assertEqual(failed, ["20260906_0226_SIOT1_BRA_YG.bin"])


class MainWiringTests(unittest.TestCase):
    """De nada adianta converter bem se o main() nunca chamar a conversao."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.bin_dir = os.path.join(self.root, "traces-bin")
        self.txt_dir = os.path.join(self.root, "traces-txt")
        self.name = "20260907_0228_SIOT1_BRA.bin"
        self.seen = []

    def _run(self, *extra_argv):
        def spy(names, bin_dir, txt_dir, db_path, convert=None, force=False):
            self.seen.append((list(names), bin_dir, txt_dir, db_path, force))
            return [os.path.splitext(n)[0] + ".txt" for n in names], []

        argv = ["sync_traces.py", "--local-dir", self.bin_dir,
                "--txt-dir", self.txt_dir, *extra_argv]
        with mock.patch.object(sync_traces, "list_remote",
                               return_value=[(self.name, 10, None)]),              mock.patch.object(sync_traces, "fetch"),              mock.patch.object(sync_traces, "commit", return_value=([self.name], [])),              mock.patch.object(sync_traces, "convert_bins", side_effect=spy),              mock.patch.object(sync_traces, "find_trace_db", return_value="db.tar.gz"),              mock.patch.object(sys, "argv", argv):
            return sync_traces.main()

    def test_converts_every_bin_it_just_downloaded(self):
        rc = self._run()
        self.assertEqual(rc, 0)
        self.assertEqual(len(self.seen), 1)
        names, bin_dir, txt_dir, db_path, force = self.seen[0]
        self.assertEqual(names, [self.name])
        self.assertEqual(os.path.abspath(bin_dir), os.path.abspath(self.bin_dir))
        self.assertEqual(os.path.abspath(txt_dir), os.path.abspath(self.txt_dir))
        self.assertEqual(db_path, "db.tar.gz")

    def test_a_freshly_downloaded_bin_is_converted_even_over_a_newer_txt(self):
        # bytes novos: o .txt existente esta obsoleto por definicao. E o .bin
        # carrega o mtime da captura, entao parece mais velho que o .txt.
        self._run()
        self.assertTrue(self.seen[0][4])

    def test_force_convert_also_redoes_the_files_already_present(self):
        os.makedirs(self.bin_dir, exist_ok=True)
        antigo = "20260907_0228_SIOT1_BRA_KY.bin"
        with open(os.path.join(self.bin_dir, antigo), "wb") as fh:
            fh.write(b"x" * 10)

        def spy(names, bin_dir, txt_dir, db_path, convert=None, force=False):
            self.seen.append((list(names), bin_dir, txt_dir, db_path, force))
            return [], []

        argv = ["sync_traces.py", "--local-dir", self.bin_dir,
                "--txt-dir", self.txt_dir, "--force-convert"]
        with mock.patch.object(sync_traces, "list_remote",
                               return_value=[(self.name, 10, None), (antigo, 10, None)]), \
             mock.patch.object(sync_traces, "fetch"), \
             mock.patch.object(sync_traces, "commit", return_value=([self.name], [])), \
             mock.patch.object(sync_traces, "convert_bins", side_effect=spy), \
             mock.patch.object(sync_traces, "find_trace_db", return_value="db.tar.gz"), \
             mock.patch.object(sys, "argv", argv):
            sync_traces.main()
        self.assertEqual(sorted(self.seen[0][0]), sorted([self.name, antigo]))

    def test_no_convert_skips_the_conversion(self):
        self.assertEqual(self._run("--no-convert"), 0)
        self.assertEqual(self.seen, [])

    def test_trace_db_flag_wins_over_the_repository_lookup(self):
        self._run("--trace-db", "outro.tar.gz")
        self.assertEqual(self.seen[0][3], "outro.tar.gz")

    def _run_nothing_new(self, *extra_argv):
        """Remoto identico ao local: nada a baixar."""
        os.makedirs(self.bin_dir, exist_ok=True)
        with open(os.path.join(self.bin_dir, self.name), "wb") as fh:
            fh.write(b"x" * 10)
        mt = datetime(2026, 9, 8, 2, 30, 53, tzinfo=timezone.utc)

        def spy(names, bin_dir, txt_dir, db_path, convert=None, force=False):
            self.seen.append((list(names), bin_dir, txt_dir, db_path, force))
            return [], []

        argv = ["sync_traces.py", "--local-dir", self.bin_dir,
                "--txt-dir", self.txt_dir, *extra_argv]
        with mock.patch.object(sync_traces, "list_remote",
                               return_value=[(self.name, 10, mt)]), \
             mock.patch.object(sync_traces, "convert_bins", side_effect=spy), \
             mock.patch.object(sync_traces, "find_trace_db", return_value="db.tar.gz"), \
             mock.patch.object(sys, "argv", argv):
            rc = sync_traces.main()
        return rc, mt

    def test_force_convert_still_runs_when_there_is_nothing_to_download(self):
        rc, _ = self._run_nothing_new("--force-convert")
        self.assertEqual(rc, 0)
        self.assertEqual(self.seen[0][0], [self.name])

    def test_nothing_new_and_no_force_converts_nothing(self):
        rc, _ = self._run_nothing_new()
        self.assertEqual(rc, 0)
        self.assertEqual(self.seen, [])

    def test_remote_mtimes_are_restored_even_when_nothing_is_new(self):
        _, mt = self._run_nothing_new()
        self.assertAlmostEqual(
            os.path.getmtime(os.path.join(self.bin_dir, self.name)),
            mt.timestamp(), places=2)

    def test_a_failed_conversion_makes_the_exit_code_nonzero(self):
        with mock.patch.object(sync_traces, "list_remote",
                               return_value=[(self.name, 10, None)]),              mock.patch.object(sync_traces, "fetch"),              mock.patch.object(sync_traces, "commit", return_value=([self.name], [])),              mock.patch.object(sync_traces, "convert_bins",
                               return_value=([], [self.name])),              mock.patch.object(sync_traces, "find_trace_db", return_value="db.tar.gz"),              mock.patch.object(sys, "argv",
                               ["sync_traces.py", "--local-dir", self.bin_dir,
                                "--txt-dir", self.txt_dir]):
            self.assertEqual(sync_traces.main(), 1)

    def test_a_missing_trace_db_does_not_throw_away_the_download(self):
        def boom(_):
            raise sync_traces.nrf_trace.TraceError("sem trace database")

        with mock.patch.object(sync_traces, "list_remote",
                               return_value=[(self.name, 10, None)]),              mock.patch.object(sync_traces, "fetch"),              mock.patch.object(sync_traces, "commit", return_value=([self.name], [])),              mock.patch.object(sync_traces, "find_trace_db", side_effect=boom),              mock.patch.object(sys, "argv",
                               ["sync_traces.py", "--local-dir", self.bin_dir,
                                "--txt-dir", self.txt_dir]):
            self.assertEqual(sync_traces.main(), 1)


class RemoteMtimeTests(unittest.TestCase):
    """O mtime do host que capturou e a ancora de tempo dos traces sem +CCLK.

    Sem preserva-lo no download, o unico registro do fim da captura se perde e
    o trace so pode cair na epoca do cabecalho, que erra por minutos.
    """

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.name = "20260908_0231_SIOT1_BRA_KY.bin"
        self.path = make_bin(self.root, self.name)
        self.mtime = datetime(2026, 9, 8, 2, 30, 53, 136000, tzinfo=timezone.utc)

    def test_stamps_the_local_file_with_the_remote_mtime(self):
        sync_traces.apply_remote_mtimes([(self.name, 10, self.mtime)], self.root)
        self.assertAlmostEqual(os.path.getmtime(self.path),
                               self.mtime.timestamp(), places=2)

    def test_reports_only_the_files_it_actually_restamped(self):
        first = sync_traces.apply_remote_mtimes(
            [(self.name, 10, self.mtime)], self.root)
        again = sync_traces.apply_remote_mtimes(
            [(self.name, 10, self.mtime)], self.root)
        self.assertEqual(first, [self.name])
        self.assertEqual(again, [])

    def test_a_missing_local_file_is_skipped(self):
        self.assertEqual(
            sync_traces.apply_remote_mtimes([("ausente.bin", 10, self.mtime)],
                                            self.root), [])

    def test_a_remote_without_a_timestamp_is_skipped(self):
        self.assertEqual(
            sync_traces.apply_remote_mtimes([(self.name, 10, None)], self.root), [])

    def test_the_listing_carries_the_remote_mtime(self):
        d = self.mtime - datetime(1, 1, 1, tzinfo=timezone.utc)
        ticks = (d.days * 86400 + d.seconds) * 10**7 + d.microseconds * 10
        saida = f"419513|{ticks}|{self.name}".encode()
        with mock.patch.object(sync_traces.subprocess, "run",
                               return_value=mock.Mock(returncode=0, stdout=saida)):
            (nome, tamanho, mtime), = sync_traces.list_remote("h", "d", "*.bin")
        self.assertEqual(nome, "20260908_0231_SIOT1_BRA_KY.bin")
        self.assertEqual(tamanho, 419513)
        self.assertEqual(mtime, self.mtime)

    def test_a_listing_line_without_a_timestamp_still_yields_the_file(self):
        saida = b"100|nao-e-numero|algum.bin"
        with mock.patch.object(sync_traces.subprocess, "run",
                               return_value=mock.Mock(returncode=0, stdout=saida)):
            (nome, tamanho, mtime), = sync_traces.list_remote("h", "d", "*.bin")
        self.assertEqual((nome, tamanho, mtime), ("algum.bin", 100, None))

    def test_the_batch_asks_sftp_to_preserve_timestamps(self):
        linhas = sync_traces.sftp_batch(r"C:\work\x", "/tmp/in", [(self.name, 10)])
        self.assertIn("-get -p ", linhas)

    def test_the_batch_uses_an_absolute_remote_path(self):
        linhas = sync_traces.sftp_batch(r"C:\work\x", "/tmp/in", [("a.bin", 1)])
        self.assertIn('"/C:/work/x/a.bin"', linhas)


class FindTraceDbTests(unittest.TestCase):
    @unittest.skipUnless(os.path.exists(DB),
                         "trace-db nao esta no repositorio")
    def test_finds_the_tarball_in_the_repository(self):
        found = sync_traces.find_trace_db(DATA)
        self.assertTrue(os.path.basename(found).startswith("trace_db_external_"))

    def test_raises_when_no_database_is_present(self):
        with self.assertRaises(sync_traces.nrf_trace.TraceError):
            sync_traces.find_trace_db(tempfile.mkdtemp())


if __name__ == "__main__":
    unittest.main(verbosity=2)
