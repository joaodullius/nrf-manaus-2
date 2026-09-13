# -*- coding: utf-8 -*-
"""Teste de travessia C-Python: compila src/payload.c num binario de host
(via tests/harness_payload.c) e compara a saida, byte a byte, com
payload_ref.montar() -- a implementacao de referencia que o servidor da
Task 7 usa para interpretar. E essa comparacao que sustenta a tese do
lab 9: "o firmware e o servidor concordam no formato".

Procura um compilador de host nesta ordem: cc, gcc, clang, e por ultimo
cl.exe (MSVC), localizado via vswhere ou no caminho padrao de uma
instalacao "Community" do Visual Studio 2022. Antes de compilar
harness_payload.c + payload.c de verdade, testa o compilador achado com
um "hello world" minimo que so usa <stdio.h> -- isso separa dois
problemas bem diferentes:

  - nenhum compilador utilizavel (ou o cl.exe achado nao compila nem
    stdio.h, por faltar o componente "Windows SDK"/UCRT no Visual Studio):
    os testes desta suite sao PULADOS, com mensagem explicita dizendo o
    que instalar. Um teste pulado nao pode passar despercebido como se
    tivesse verificado a travessia.
  - o compilador funciona, mas harness_payload.c + payload.c nao
    compilam: isso e um erro real, e o teste FALHA.

payload.c e payload.h nao dependem de nada do Zephyr (so da biblioteca
padrao C), entao nao foi preciso nenhum cabecalho de compatibilidade nem
#define para compilar no host.
"""
from __future__ import annotations

import errno
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from payload_ref import montar

TESTS_DIR = Path(__file__).resolve().parent
LAB_DIR = TESTS_DIR.parents[1]          # comms/09_wifi_tcp
SRC_DIR = LAB_DIR / "src"
HARNESS_C = TESTS_DIR / "harness_payload.c"
PAYLOAD_C = SRC_DIR / "payload.c"

VETORES = json.loads((TESTS_DIR / "vetores_payload.json").read_text(encoding="utf-8"))
CASOS = VETORES["casos"]
TRUNCAMENTO = VETORES["truncamento"]

MSG_SEM_COMPILADOR = (
    "Nenhum compilador de host encontrado (procurei cc, gcc, clang e "
    "cl.exe). A travessia C-Python NAO foi verificada nesta execucao. "
    "Instale um compilador C para validar que src/payload.c e "
    "tools/payload_ref.py concordam byte a byte -- por exemplo, MSVC "
    "Build Tools (traz o cl.exe) ou um toolchain gcc/clang (MSYS2, "
    "w64devkit, etc.)."
)


def _achar_vcvarsall():
    """Localiza o vcvarsall.bat de uma instalacao do Visual Studio.

    Tenta primeiro o vswhere (forma oficial de descobrir instalacoes do
    VS); se o vswhere nao existir, nao achar nada, ou falhar por qualquer
    motivo, cai para o caminho padrao de uma instalacao "Community" do
    VS 2022, que e o que esta bancada usa.
    """
    program_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    vswhere = Path(program_files_x86) / "Microsoft Visual Studio" / "Installer" / "vswhere.exe"
    if vswhere.exists():
        try:
            r = subprocess.run(
                [str(vswhere), "-latest", "-products", "*",
                 "-requires", "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
                 "-property", "installationPath"],
                capture_output=True, text=True, timeout=30, check=False,
            )
            linhas = [l.strip() for l in r.stdout.splitlines() if l.strip()]
            if linhas:
                candidato = Path(linhas[0]) / "VC" / "Auxiliary" / "Build" / "vcvarsall.bat"
                if candidato.exists():
                    return candidato
        except OSError:
            pass

    fallback = (Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
                / "Microsoft Visual Studio" / "2022" / "Community"
                / "VC" / "Auxiliary" / "Build" / "vcvarsall.bat")
    if fallback.exists():
        return fallback
    return None


def _rodar_compilacao(cc, vcvarsall, fontes, out_exe: Path, build_dir: Path, include_dir: Path):
    """Compila `fontes` (lista de Path) em `out_exe`, com gcc/clang/cc se
    `cc` for informado, senao com cl.exe (MSVC) via vcvarsall. Devolve o
    CompletedProcess."""
    if cc:
        return subprocess.run(
            [cc, "-o", str(out_exe), "-I", str(include_dir)] + [str(f) for f in fontes],
            capture_output=True, text=True, timeout=60, check=False,
        )

    fontes_str = " ".join(f'"{f}"' for f in fontes)
    program_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    installer_dir = Path(program_files_x86) / "Microsoft Visual Studio" / "Installer"
    bat = build_dir / (out_exe.stem + "_compile.bat")
    bat.write_text(
        "@echo off\r\n"
        # vcvarsall.bat chama o vswhere.exe internamente para achar o SDK;
        # sem isso no PATH, ele falha calado e pode nem configurar o SDK.
        f'set "PATH=%PATH%;{installer_dir}"\r\n'
        f'call "{vcvarsall}" x64 >nul\r\n'
        f'cl.exe /nologo /I"{include_dir}" /Fe:"{out_exe}" {fontes_str}\r\n',
        encoding="utf-8",
    )
    return subprocess.run(["cmd.exe", "/c", str(bat)], capture_output=True, text=True,
                           timeout=90, cwd=str(build_dir), check=False)


def _compilar(build_dir: Path):
    """Acha um compilador de host, confirma que ele compila um C minimo, e
    entao compila harness_payload.c + payload.c.

    Devolve (caminho_do_binario, descricao_do_compilador). Chama
    pytest.skip() se nenhum compilador utilizavel for encontrado (nenhum
    achado, ou o cl.exe achado nao compila nem <stdio.h> por faltar o
    Windows SDK), ou pytest.fail() se o compilador funciona mas
    harness_payload.c + payload.c derem erro de verdade.
    """
    cc = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    vcvarsall = None
    if cc:
        descricao = cc
    else:
        vcvarsall = _achar_vcvarsall()
        if vcvarsall is None:
            pytest.skip(MSG_SEM_COMPILADOR)
        descricao = f"cl.exe (MSVC, via {vcvarsall})"

    # Probe: confirma que da para compilar ate um "hello world" com
    # <stdio.h>, antes de tentar harness_payload.c + payload.c de verdade.
    # Sem isso, uma maquina com o VC++ Build Tools instalado mas sem o
    # componente "Windows SDK" (UCRT) tem cl.exe no disco, mas ele nao
    # acha nem stdio.h -- e isso nao e um bug em payload.c.
    probe_c = build_dir / "_probe.c"
    probe_c.write_text('#include <stdio.h>\nint main(void) { printf("ok"); return 0; }\n',
                        encoding="utf-8")
    probe_exe = build_dir / ("_probe.exe" if os.name == "nt" else "_probe")
    r_probe = _rodar_compilacao(cc, vcvarsall, [probe_c], probe_exe, build_dir, SRC_DIR)
    if r_probe.returncode != 0 or not probe_exe.exists():
        pytest.skip(
            f"{descricao} foi encontrado, mas nao compila nem um C minimo "
            "com <stdio.h>. Provavelmente falta o Windows SDK / UCRT "
            "(instale o componente \"Windows 10/11 SDK\" pelo Visual "
            "Studio Installer), ou o toolchain gcc/clang esta incompleto. "
            "A travessia C-Python NAO foi verificada nesta execucao.\n"
            f"--- saida do compilador ---\n{r_probe.stdout}\n{r_probe.stderr}"
        )

    out_exe = build_dir / ("harness_payload.exe" if os.name == "nt" else "harness_payload")
    r = _rodar_compilacao(cc, vcvarsall, [HARNESS_C, PAYLOAD_C], out_exe, build_dir, SRC_DIR)
    if r.returncode != 0 or not out_exe.exists():
        pytest.fail(
            f"O compilador funciona (o probe com <stdio.h> passou), mas "
            f"falhou ao compilar harness_payload.c + payload.c com "
            f"{descricao} -- isso e provavelmente um erro real no codigo:\n"
            f"--- stdout ---\n{r.stdout}\n--- stderr ---\n{r.stderr}"
        )
    return out_exe, descricao


@pytest.fixture(scope="session")
def payload_c_bin(tmp_path_factory):
    build_dir = tmp_path_factory.mktemp("payload_c_build")
    return _compilar(build_dir)


def _rodar_harness(exe: Path, caso: dict, buf_len=None):
    args = [str(exe), str(caso["seq"]), str(caso["uptime_ms"]), str(caso["temp_cc"]),
            str(caso["rssi_dbm"]), "1" if caso["botao"] else "0"]
    if buf_len is not None:
        args.append(str(buf_len))
    return subprocess.run(args, capture_output=True, timeout=10, check=False)


def test_compilador_encontrado(payload_c_bin):
    exe, descricao = payload_c_bin
    assert exe.exists()
    print(f"\nTravessia C-Python: compilador usado = {descricao}")


@pytest.mark.parametrize("caso", CASOS, ids=[c["nome"] for c in CASOS])
def test_c_e_python_concordam_byte_a_byte(payload_c_bin, caso):
    exe, _ = payload_c_bin
    r = _rodar_harness(exe, caso)
    assert r.returncode == 0, f"harness_payload falhou: {r.stderr!r}"
    saida_c = r.stdout

    saida_py = montar(seq=caso["seq"], uptime_ms=caso["uptime_ms"], temp_cc=caso["temp_cc"],
                       rssi_dbm=caso["rssi_dbm"], botao=caso["botao"]).encode("utf-8")

    assert saida_c == saida_py, f"C:      {saida_c!r}\nPython: {saida_py!r}"


def test_c_trunca_buffer_pequeno_e_devolve_enomem(payload_c_bin):
    exe, _ = payload_c_bin
    t = TRUNCAMENTO
    r = _rodar_harness(exe, t, buf_len=t["buf_len"])
    assert r.returncode == 0, f"harness_payload falhou: {r.stderr!r}"
    saida = r.stdout.decode("utf-8").strip()
    assert saida.startswith("ERRO:"), f"esperava 'ERRO:<n>', veio {saida!r}"
    n = int(saida.split(":", 1)[1])
    assert n == -errno.ENOMEM
