#!/usr/bin/env python3
"""
build_all.py — gera os .hex de referencia de cada passo do modulo Edge AI.

Cada variante e compilada PRISTINE num build dir proprio (build/hex/<nome>),
com as edicoes temporarias que o passo exige (fundo de escala do 05, blocos do
04, endereco do tag no 03) aplicadas antes e desfeitas depois — os fontes do
repo ficam exatamente como estavam, mesmo se um build falhar.

Uso (de qualquer pasta):
    python edge_ai/hex/build_all.py            # todas as variantes
    python edge_ai/hex/build_all.py 04 05      # so as que comecam com 04 ou 05
    python edge_ai/hex/build_all.py --list

Requisitos: nRF Connect SDK v3.4.0 via nrfutil sdk-manager, e o workspace do
Edge AI Add-on em C:/ncs/sdk-edge-ai (o west roda de la).
"""

import io
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
EDGE = REPO / "edge_ai"
HEX = EDGE / "hex"
BUILD = REPO / "build" / "hex"
NCS_WS = Path(r"C:/ncs/sdk-edge-ai")
NCS_VER = "v3.4.0"

TAG = "nrf54l15tag/nrf54l15/cpuapp"
LM20 = "nrf54lm20dk/nrf54lm20b/cpuapp"

# Endereco da TAG da bancada de referencia. Os hex do 03 filtram por ele.
TAG_ADDR_VALUE = "EC:EF:40:2D:5E:46"
TAG_ADDR_TYPE = "random"


# --------------------------------------------------------------- edicoes
class Edit:
    """Edicao temporaria num arquivo: aplica antes do build, restaura depois."""

    def __init__(self, path, apply_fn):
        self.path = Path(path)
        self.apply_fn = apply_fn
        self.original = None

    def apply(self):
        # newline="" preserva CRLF/LF exatamente como estao no arquivo
        self.original = io.open(self.path, encoding="utf-8", newline="").read()
        new = self.apply_fn(self.original)
        if new == self.original:
            raise RuntimeError(f"edicao nao teve efeito em {self.path}")
        io.open(self.path, "w", encoding="utf-8", newline="").write(new)

    def restore(self):
        if self.original is not None:
            io.open(self.path, "w", encoding="utf-8", newline="").write(self.original)
            self.original = None


def sub_once(pattern, repl):
    def fn(s):
        new, n = re.subn(pattern, repl, s, count=1, flags=re.M)
        if n != 1:
            raise RuntimeError(f"padrao nao encontrado: {pattern}")
        return new
    return fn


def edit_01_modelo(nome):
    return Edit(EDGE / "01_gesture_recognition" / "CMakeLists.txt",
                sub_once(r'^set\(CURSO_MODELO "fabrica"\)', f'set(CURSO_MODELO "{nome}")'))


def edit_05_escala():
    def fn(s):
        s2 = s.replace("full_scale.val1 = 2; /* G */", "full_scale.val1 = 4; /* G */", 1)
        s2 = s2.replace("full_scale.val1 = 500; /* dps */", "full_scale.val1 = 1000; /* dps */", 1)
        return s2
    return Edit(EDGE / "05_data_forwarder" / "src" / "sensor" / "bmi270.c", fn)


def edit_04_cmake_ventilador():
    return Edit(EDGE / "04_classify_led" / "CMakeLists.txt",
                sub_once(r'^set\(CURSO_MODELO "Neuton"\)', 'set(CURSO_MODELO "ventilador_95922")'))


def edit_04_main_ventilador():
    """Comenta o bloco Neuton (constantes + cores) e descomenta o do ventilador."""
    def fn(s):
        for macro in ("USER_WINDOW_SIZE", "USER_UNIQ_INPUTS_NUM", "USER_MODELS_CLASS_NUM"):
            s, n1 = re.subn(rf'^#define {macro} ', f'// #define {macro} ', s, count=1, flags=re.M)
            s, n2 = re.subn(rf'^// #define {macro} (\s*\d+U)', rf'#define {macro} \1', s, count=1, flags=re.M)
            if n1 != 1 or n2 != 1:
                raise RuntimeError(f"bloco de {macro} nao encontrado")
        a = s.index("/* Neuton (exemplo da Nordic): estados de transporte")
        b = s.index("/* ventilador_95922 (modelo do curso): na ordem")
        c = s.index("// };", b) + len("// };")
        neuton = s[a:b]
        vent = s[b:c]
        neuton_c = "\n".join(("// " + l if l.strip() and not l.startswith("/*") else l)
                             for l in neuton.split("\n"))
        vent_u = "\n".join((l[3:] if l.startswith("// ") else l) for l in vent.split("\n"))
        return s[:a] + neuton_c + vent_u + s[c:]
    return Edit(EDGE / "04_classify_led" / "src" / "main.c", fn)


def conf_03_tag():
    """Fragmento com o endereco da TAG de referencia, fora do repo."""
    p = BUILD / "meu_tag_referencia.conf"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f'CONFIG_LAB_TAG_ADDR_VALUE="{TAG_ADDR_VALUE}"\n'
                 f'CONFIG_LAB_TAG_ADDR_TYPE="{TAG_ADDR_TYPE}"\n', encoding="utf-8")
    return str(p).replace("\\", "/")


# --------------------------------------------------------------- variantes
# nome do hex (sem extensao), app, board, extra args do west, edicoes temporarias
VARIANTES = [
    ("01_gesture_fabrica_tag", "01_gesture_recognition", TAG,
     ["--sysbuild"], []),
    ("01_gesture_coleta_tag", "01_gesture_recognition", TAG,
     ["--sysbuild", "--", "-DEXTRA_CONF_FILE=data_collection.conf"], []),
    ("01_gesture_manaus_4gestos_tag", "01_gesture_recognition", TAG,
     ["--sysbuild"], [lambda: edit_01_modelo("manaus_4gestos")]),
    ("02_anomaly_lm20dk", "02_anomaly", LM20,
     ["--sysbuild"], []),
    ("03_central_uart_texto_lm20dk", "03_central_uart", LM20,
     ["--", lambda: f"-DEXTRA_CONF_FILE={conf_03_tag()}"], []),
    ("03_central_uart_binario_lm20dk", "03_central_uart", LM20,
     ["--", lambda: f"-DEXTRA_CONF_FILE={conf_03_tag()};binary_bridge.conf"], []),
    ("04_classify_led_neuton_tag", "04_classify_led", TAG,
     [], []),
    ("04_classify_led_ventilador_tag", "04_classify_led", TAG,
     [], [edit_04_cmake_ventilador, edit_04_main_ventilador]),
    ("05_data_forwarder_sample_tag", "05_data_forwarder", TAG,
     [], []),
    ("05_data_forwarder_4g_tag", "05_data_forwarder", TAG,
     [], [edit_05_escala]),
    ("06_mic_check_lm20dk", "06_mic_check", LM20,
     ["--sysbuild"], []),
    ("07_ww_kws_lm20dk", "07_ww_kws", LM20,
     ["--sysbuild"], []),
    ("08_cough_detection_lm20dk", "08_cough_detection", LM20,
     ["--sysbuild"], []),
    ("09_dog_bark_detection_lm20dk", "09_dog_bark_detection", LM20,
     ["--sysbuild"], []),
    ("10_sound_events_lm20dk", "10_sound_events", LM20,
     ["--sysbuild"], []),
]


def west(args):
    cmd = ["nrfutil", "sdk-manager", "toolchain", "launch", "--ncs-version", NCS_VER, "--",
           "west"] + args
    return subprocess.run(cmd, cwd=str(NCS_WS), capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def acha_hex(build_dir, app):
    for cand in (build_dir / "merged.hex",
                 build_dir / Path(app).name / "zephyr" / "zephyr.hex",
                 build_dir / "zephyr" / "zephyr.hex"):
        if cand.exists():
            return cand
    raise FileNotFoundError(f"nenhum hex em {build_dir}")


def tamanho(log):
    m = re.search(r"FLASH:\s+(\d+) B.*?RAM:\s+(\d+) B", log, re.S)
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


def build(nome, app, board, extra, edits):
    build_dir = BUILD / nome
    app_dir = EDGE / app
    aplicadas = []
    try:
        for e in edits:
            ed = e()
            ed.apply()
            aplicadas.append(ed)
        args = ["build", "-p", "-b", board, "-d", str(build_dir).replace("\\", "/"),
                str(app_dir).replace("\\", "/")]
        args += [a() if callable(a) else a for a in extra]
        r = west(args)
        log = r.stdout + r.stderr
        if r.returncode != 0:
            (HEX / f"{nome}.log").write_text(log, encoding="utf-8")
            raise RuntimeError(f"west build falhou (log em hex/{nome}.log)")
        src = acha_hex(build_dir, app)
        HEX.mkdir(exist_ok=True)
        shutil.copyfile(src, HEX / f"{nome}.hex")
        return tamanho(log), src.name
    finally:
        for ed in reversed(aplicadas):
            ed.restore()


def main():
    argv = sys.argv[1:]
    if "--list" in argv:
        for v in VARIANTES:
            print(v[0])
        return
    sel = [v for v in VARIANTES if not argv or any(v[0].startswith(p) for p in argv)]
    if not sel:
        sys.exit("nenhuma variante casa com " + " ".join(argv))
    print(f"{len(sel)} variante(s) → {HEX}")
    falhas = 0
    for nome, app, board, extra, edits in sel:
        print(f"\n=== {nome}  ({app} · {board})", flush=True)
        try:
            (flash, ram), origem = build(nome, app, board, extra, edits)
            print(f"    ok  {origem}  flash {flash:,} B  ram {ram:,} B".replace(",", "."))
        except Exception as ex:  # noqa: BLE001
            falhas += 1
            print(f"    FALHOU: {ex}")
    print(f"\n{len(sel) - falhas} ok, {falhas} falha(s)")
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
