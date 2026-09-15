#!/usr/bin/env python3
"""Testes do center_host.py com um CSV sintetico no formato do Host.

    python tools/test_center_host.py
"""
import csv
import math
import os
import random
import subprocess
import sys
import tempfile
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(AQUI, "center_host.py")
HEADER = ["device_time_ms", "ax", "ay", "az", "gx", "gy", "gz",
          "temp", "hum", "pres", "label"]


def grava_host(caminho, n_gestos=30, pausa=150, largura=40, label="swipe_left",
               fs_ms=10, borda=500):
    """Gestos: pulso de meio seno em gz (micro rad/s), ruido no resto."""
    random.seed(1)
    linhas = []
    t = 0

    def linha(gz):
        nonlocal t
        t += fs_ms
        return [t, random.randint(-50000, 50000), random.randint(-50000, 50000),
                10_000_000 + random.randint(-50000, 50000),
                random.randint(-3000, 3000), random.randint(-3000, 3000),
                float(gz + random.randint(-3000, 3000)),
                24030000.0, 55000000.0, 100900000.0, label]

    for _ in range(borda):
        linhas.append(linha(0))
    for _ in range(n_gestos):
        for _ in range(pausa):
            linhas.append(linha(0))
        for k in range(largura):
            linhas.append(linha(2_000_000 * math.sin(math.pi * k / largura)))
    for _ in range(borda):
        linhas.append(linha(0))
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        w.writerows(linhas)
    return len(linhas)


def roda(*args):
    return subprocess.run([sys.executable, SCRIPT, *args],
                          capture_output=True, text=True)


class CenterHost(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.entrada = os.path.join(self.tmp.name, "swipe_left_ble-abc.csv")
        self.n_linhas = grava_host(self.entrada)

    def tearDown(self):
        self.tmp.cleanup()

    def test_saida_no_formato_do_host(self):
        r = roda(self.entrada, "-w", "100")
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        saida = os.path.join(self.tmp.name, "swipe_left_ble-abc_centrado.csv")
        self.assertTrue(os.path.exists(saida), r.stdout)
        with open(saida, newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))
        self.assertEqual(rows[0], HEADER)
        dados = rows[1:]
        self.assertGreaterEqual(len(dados) // 100, 20)
        self.assertEqual(len(dados) % 100, 0)
        self.assertTrue(all(r[-1] == "swipe_left" for r in dados))
        self.assertLess(len(dados), self.n_linhas)
        # cada janela tem o pico de gz perto do meio
        for i in range(0, len(dados), 100):
            gz = [abs(float(r[6])) for r in dados[i:i + 100]]
            pico = gz.index(max(gz))
            self.assertTrue(30 <= pico < 70, f"janela {i // 100}: pico em {pico}")

    def test_opcao_o(self):
        saida = os.path.join(self.tmp.name, "x.csv")
        r = roda(self.entrada, "-o", saida)
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertTrue(os.path.exists(saida))

    def test_recusa_header_estranho(self):
        ruim = os.path.join(self.tmp.name, "ruim.csv")
        with open(ruim, "w", newline="") as f:
            f.write("acc_x,acc_y,acc_z,gyro_x,gyro_y,gyro_z,class\n1,2,3,4,5,6,0\n")
        r = roda(ruim)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("header", r.stderr)

    def test_recusa_duas_classes(self):
        with open(self.entrada, "a", newline="") as f:
            f.write("999999,0,0,0,0,0,0,0,0,0,outra\n")
        r = roda(self.entrada)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("label", r.stderr)

    def test_recusa_janela_impar(self):
        r = roda(self.entrada, "-w", "99")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("impar", r.stderr)


if __name__ == "__main__":
    unittest.main()
