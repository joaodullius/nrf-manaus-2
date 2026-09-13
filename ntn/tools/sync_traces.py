#!/usr/bin/env python3
"""Copy .bin trace files from a remote Windows machine over SSH, incrementally.

Lists the remote directory via `ssh ... powershell -EncodedCommand`, compares
against the local folder by name + size, and fetches only what is missing (or
what came over truncated last time) in a single `sftp -b` session.

    python sync_traces.py
    python sync_traces.py --dry-run
    python sync_traces.py --host dulli@192.168.15.9 --remote-dir "C:/work/nrf-ntn-priv"
"""

import argparse
import base64
from datetime import datetime, timedelta, timezone
import glob
import os
import shutil
import subprocess
import sys
import tempfile

import nrf_trace

DEFAULT_HOST = "dulli@192.168.15.9"
DEFAULT_REMOTE_DIR = r"C:\work\nrf-ntn-priv"
DEFAULT_LOCAL_DIR = "traces-bin"
DEFAULT_PATTERN = "*.bin"
DEFAULT_TXT_DIR = "traces-txt"

SSH_OPTS = ["-o", "ConnectTimeout=10"]


def ps_quote(value):
    """Quote a string for a PowerShell single-quoted literal."""
    return "'" + value.replace("'", "''") + "'"


def encode_ps(script):
    """Encode a PowerShell script for -EncodedCommand (UTF-16LE + base64)."""
    return base64.b64encode(script.encode("utf-16-le")).decode("ascii")


def list_remote(host, remote_dir, pattern):
    """Return [(name, size, mtime_utc)] for files matching pattern remotely."""
    script = (
        "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; "
        "$ErrorActionPreference='Stop'; "
        f"Get-ChildItem -LiteralPath {ps_quote(remote_dir)} -Filter {ps_quote(pattern)} -File "
        '| ForEach-Object { "$($_.Length)|$($_.LastWriteTimeUtc.Ticks)|$($_.Name)" }'
    )
    cmd = ["ssh", *SSH_OPTS, host, "powershell", "-NoProfile", "-NonInteractive",
           "-EncodedCommand", encode_ps(script)]

    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0:
        stderr = proc.stderr.decode("utf-8", "replace").strip()
        raise SystemExit(
            f"Falha ao listar o remoto (ssh saiu com {proc.returncode}).\n"
            f"{stderr}\n"
            "Confira o host, a pasta remota e se a maquina remota e Windows com PowerShell."
        )

    files = []
    for line in proc.stdout.decode("utf-8", "replace").splitlines():
        line = line.strip()
        if not line:
            continue
        partes = line.split("|", 2)
        if len(partes) != 3:
            continue
        size, mtime, name = partes
        if not name:
            continue
        try:
            files.append((name, int(size), _ticks_to_utc(mtime)))
        except ValueError:
            print(f"  ! linha inesperada do remoto, ignorando: {line}")
    return files


def plan(files, local_dir):
    """Split remote files into (to_fetch, skipped) based on local name + size."""
    to_fetch, skipped = [], []
    for name, size, _mtime in sorted(files, key=lambda f: f[0]):
        local_path = os.path.join(local_dir, name)
        if os.path.isfile(local_path):
            local_size = os.path.getsize(local_path)
            if local_size == size:
                skipped.append(name)
                print(f"  = ja existe   {name} ({size} bytes)")
                continue
            print(f"  ~ tamanho difere {name} (local {local_size} != remoto {size}), refazendo")
        else:
            print(f"  + novo        {name} ({size} bytes)")
        to_fetch.append((name, size))
    return to_fetch, skipped


_TICKS_EPOCH = datetime(1, 1, 1, tzinfo=timezone.utc)


def _ticks_to_utc(value):
    """Converte o LastWriteTimeUtc.Ticks do PowerShell (100 ns desde 0001-01-01)."""
    try:
        ticks = int(value)
    except ValueError:
        return None
    return _TICKS_EPOCH + timedelta(microseconds=ticks // 10)


def apply_remote_mtimes(files, local_dir):
    """Carimba os arquivos locais com o mtime da maquina que capturou.

    Para um trace sem +CCLK esse mtime e a unica ancora de tempo absoluto que
    sobra: marca o fechamento do arquivo, poucos segundos depois do ultimo
    registro. A epoca gravada no cabecalho do .bin nao serve, porque marca o
    inicio da captura, com o modem ainda dormindo. Devolve os nomes ajustados.
    """
    ajustados = []
    for name, _size, mtime in files:
        path = os.path.join(local_dir, name)
        if mtime is None or not os.path.isfile(path):
            continue
        alvo = mtime.timestamp()
        if abs(os.path.getmtime(path) - alvo) > 1:
            os.utime(path, (alvo, alvo))
            ajustados.append(name)
    return ajustados


def sftp_batch(remote_dir, incoming_dir, to_fetch):
    """Monta o script do `sftp -b` que baixa a fila numa sessao so."""
    remote_base = remote_dir.replace("\\", "/").rstrip("/")
    # O sftp do OpenSSH no Windows resolve "C:/..." como relativo ao home;
    # o caminho absoluto precisa da barra na frente: "/C:/...".
    if len(remote_base) > 1 and remote_base[1] == ":":
        remote_base = "/" + remote_base
    lines = []
    for name, _ in to_fetch:
        remote_path = f"{remote_base}/{name}"
        local_path = os.path.join(incoming_dir, name).replace("\\", "/")
        # '-' na frente: segue adiante se uma transferencia falhar.
        # '-p': preserva o mtime, que e a ancora de tempo do trace.
        lines.append(f'-get -p "{remote_path}" "{local_path}"')
    return "\n".join(lines) + "\n"


def fetch(host, remote_dir, incoming_dir, to_fetch):
    """Download the queued files in a single sftp batch session."""
    batch = tempfile.NamedTemporaryFile("w", suffix=".sftp", delete=False,
                                        encoding="utf-8", newline="\n")
    try:
        batch.write(sftp_batch(remote_dir, incoming_dir, to_fetch))
        batch.close()
        subprocess.run(["sftp", *SSH_OPTS, "-b", batch.name, host])
    finally:
        os.unlink(batch.name)


def commit(to_fetch, incoming_dir, local_dir):
    """Move fully-transferred files into place; drop partials. Returns (ok, failed)."""
    ok, failed = [], []
    for name, size in to_fetch:
        staged = os.path.join(incoming_dir, name)
        if os.path.isfile(staged) and os.path.getsize(staged) == size:
            os.replace(staged, os.path.join(local_dir, name))
            ok.append(name)
        else:
            got = os.path.getsize(staged) if os.path.isfile(staged) else 0
            print(f"  ! incompleto  {name} ({got}/{size} bytes) - sera refeito na proxima rodada")
            if os.path.isfile(staged):
                os.unlink(staged)
            failed.append(name)
    return ok, failed


def find_trace_db(repo_dir):
    """Localiza o trace database .tar.gz do repositorio."""
    hits = sorted(glob.glob(os.path.join(repo_dir, "trace_db_external_*.tar.gz")))
    if not hits:
        raise nrf_trace.TraceError(
            f"nenhum trace_db_external_*.tar.gz em {repo_dir}; use --trace-db"
        )
    return hits[-1]


def convert_bins(names, bin_dir, txt_dir, db_path, convert=None, force=False):
    """Converte cada .bin para traces-txt mantendo o nome base.

    Devolve (convertidos, falhados). Uma falha nao interrompe as demais.
    """
    if convert is None:
        convert = nrf_trace.convert
    os.makedirs(txt_dir, exist_ok=True)
    done, failed = [], []
    for name in names:
        bin_path = os.path.join(bin_dir, name)
        txt_name = os.path.splitext(name)[0] + ".txt"
        txt_path = os.path.join(txt_dir, txt_name)
        if not force and os.path.isfile(txt_path):
            if os.path.getmtime(txt_path) >= os.path.getmtime(bin_path):
                print(f"  = txt atual   {txt_name}")
                continue
        try:
            nrf_trace.write_txt(convert(bin_path, db_path), txt_path)
        except Exception as e:
            print(f"  ! falhou      {name}: {e}")
            failed.append(name)
        else:
            print(f"  > convertido  {txt_name}")
            done.append(txt_name)
    return done, failed


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", default=DEFAULT_HOST, help="user@host SSH (default: %(default)s)")
    parser.add_argument("--remote-dir", default=DEFAULT_REMOTE_DIR,
                        help="pasta remota (default: %(default)s)")
    parser.add_argument("--local-dir", default=DEFAULT_LOCAL_DIR,
                        help="pasta local de destino (default: %(default)s)")
    parser.add_argument("--pattern", default=DEFAULT_PATTERN,
                        help="filtro de arquivos (default: %(default)s)")
    parser.add_argument("--dry-run", action="store_true",
                        help="so mostra o que seria copiado")
    parser.add_argument("--txt-dir", default=DEFAULT_TXT_DIR,
                        help="pasta dos .txt convertidos (default: %(default)s)")
    parser.add_argument("--trace-db", default=None,
                        help="trace database .tar.gz (default: o do repositorio)")
    parser.add_argument("--no-convert", action="store_true",
                        help="nao converter os .bin novos para .txt")
    parser.add_argument("--force-convert", action="store_true",
                        help="reconverter mesmo se o .txt ja estiver atualizado")
    args = parser.parse_args()

    local_dir = os.path.abspath(args.local_dir)
    os.makedirs(local_dir, exist_ok=True)

    print(f"Remoto : {args.host}:{args.remote_dir} ({args.pattern})")
    print(f"Local  : {local_dir}\n")

    files = list_remote(args.host, args.remote_dir, args.pattern)
    if not files:
        print("Nenhum arquivo encontrado no remoto.")
        return 0
    print(f"{len(files)} arquivo(s) no remoto:\n")

    to_fetch, skipped = plan(files, local_dir)

    bad = [n for n, _ in to_fetch if '"' in n]
    if bad:
        print(f"\n! ignorando {len(bad)} arquivo(s) com aspas no nome: {', '.join(bad)}")
        to_fetch = [(n, s) for n, s in to_fetch if '"' not in n]

    # Antes de qualquer saida antecipada: o mtime remoto e a ancora de tempo dos
    # traces sem +CCLK, entao vale restaurar mesmo numa rodada sem novidade.
    ajustados = apply_remote_mtimes(files, local_dir)
    if ajustados:
        print(f"\n  mtime remoto restaurado em {len(ajustados)} arquivo(s)")

    if args.dry_run:
        total = sum(size for _, size in to_fetch)
        print(f"\n[dry-run] copiaria {len(to_fetch)} arquivo(s), {total/1e6:.1f} MB.")
        return 0

    ok, failed = [], []
    if to_fetch:
        incoming_dir = os.path.join(local_dir, ".incoming")
        os.makedirs(incoming_dir, exist_ok=True)
        print(f"\nBaixando {len(to_fetch)} arquivo(s)...\n")
        fetch(args.host, args.remote_dir, incoming_dir, to_fetch)
        ok, failed = commit(to_fetch, incoming_dir, local_dir)
        shutil.rmtree(incoming_dir, ignore_errors=True)
        print(f"\n{len(ok)} copiado(s), {len(skipped)} pulado(s), {len(failed)} falhou(ram).")
    else:
        print(f"\nNada novo. {len(skipped)} arquivo(s) ja estavam aqui.")

    # Arquivos recem-baixados sao bytes novos: sempre reconverte. Com
    # --force-convert, refaz tambem os que ja estavam aqui -- util quando a
    # regra de ancoragem muda e os .txt antigos precisam ser regerados.
    alvos = list(ok) + (skipped if args.force_convert else [])
    if args.no_convert or not alvos:
        return 1 if failed else 0

    txt_dir = os.path.abspath(args.txt_dir)
    try:
        db_path = args.trace_db or find_trace_db(os.path.dirname(os.path.abspath(__file__)))
    except nrf_trace.TraceError as e:
        # O download ja esta salvo em disco; so a conversao fica pendente.
        print(f"\n! sem trace database, nada convertido: {e}")
        return 1

    print(f"\nConvertendo {len(alvos)} arquivo(s) para {txt_dir}...\n")
    converted, conv_failed = convert_bins(alvos, local_dir, txt_dir, db_path, force=True)
    print(f"\n{len(converted)} convertido(s), {len(conv_failed)} sem converter.")
    return 1 if failed or conv_failed else 0


if __name__ == "__main__":
    sys.exit(main())
