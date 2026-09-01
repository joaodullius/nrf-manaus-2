#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Centraliza gestos discretos na janela de treino, com calibracao automatica.

Codigo do curso. O ALGORITMO nao e nosso: as funcoes vem do script da Nordic em
tools/segment-center-signal/segment_data_around_peaks.py, carregadas daqui sem
copia. O que este script acrescenta e a automacao em volta:

    1. escolhe o eixo de trabalho e o threshold_coef POR MEDICAO, varrendo as
       combinacoes e pontuando cada uma por onde o pico cai dentro da janela
    2. imprime a tabela da varredura — a escolha fica auditavel, nao magica
    3. valida o header do Lab na entrada e devolve o header na saida
    4. garante saida multipla da janela e protege contra o iloc negativo
    5. modo --continuo para idle/unknown: so apara para multiplo da janela

Por que calibrar: o threshold_coef=0.5 do exemplo da Nordic e calibrado para a
gravacao DELES. Medido no swipe_right de 2026-09-01, ele deixa 12% dos gestos
centrados; 0.95 deixa 71%. E a faixa util e estreita — acima de ~1.05 os gestos
mais fracos somem em silencio.

Uso:
    # gesto discreto, tudo automatico
    python tools/center_gestures.py dataset/swipe_right_*.csv

    # fixando o que voce ja sabe
    python tools/center_gestures.py dataset/swipe_left_*.csv --axis gyro_z --coef 0.9

    # classes continuas: so apara para multiplo da janela
    python tools/center_gestures.py dataset/idle_*.csv dataset/unknown_*.csv --continuo

Depois:
    python tools/prep_dataset.py merge "dataset_centered/*.csv" --out dataset_centrado.csv

Requisitos: pandas, numpy (os mesmos do script da Nordic).
"""

from __future__ import annotations

import argparse
import glob
import os
import statistics as st
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.abspath(os.path.join(AQUI, ".."))          # 03_central_uart/
NORDIC = os.path.join(AQUI, "segment-center-signal", "segment_data_around_peaks.py")

# O nome de saida vem do rotulo do dado, nao do nome do arquivo. Fonte unica:
# o mesmo dicionario que o prep_dataset.py usa para gravar (import seguro, ele
# tem guarda de __main__).
sys.path.insert(0, AQUI)
from prep_dataset import CLASSES                                   # noqa: E402

NOME_POR_ROTULO = {v: k for k, v in CLASSES.items()}

# Marcador que separa as funcoes do bloco de execucao no arquivo da Nordic.
MARCADOR = "# BLOCO DE EXECUCAO"

COLUNAS_LAB = ["acc_x", "acc_y", "acc_z", "gyro_x", "gyro_y", "gyro_z", "class"]
# Nomes internos que as funcoes da Nordic esperam (config['work_axis']).
COLUNAS_NORDIC = ["aX", "aY", "aZ", "gX", "gY", "gZ", "target"]
LAB_PARA_NORDIC = dict(zip(COLUNAS_LAB, COLUNAS_NORDIC))

# Candidatos a eixo de trabalho. So giroscopios: eles repousam em zero, entao a
# remocao de DC do algoritmo vira no-op e a pausa entre gestos da envelope quase
# nulo — que e o que o limiar precisa. Os acelerometros carregam a gravidade
# (acc_z ~ 10012 parado), que vira um degrau constante na pausa.
EIXOS_CANDIDATOS = ["gyro_x", "gyro_y", "gyro_z"]

GRADE_COEF = [round(0.50 + 0.05 * i, 2) for i in range(17)]   # 0.50 .. 1.30

MIN_GESTOS = 20     # o Lab exige >= 20 amostras por classe


def morrer(msg: str):
    print(f"erro: {msg}", file=sys.stderr)
    raise SystemExit(1)


def carrega_funcoes_nordic():
    """Executa SO a parte de funcoes do script da Nordic e devolve o namespace.

    Nao importamos o modulo: o bloco de execucao do fim roda no import (le CSV,
    cria figuras). Cortamos no marcador e executamos so o que vem antes.
    """
    if not os.path.exists(NORDIC):
        morrer(f"script da Nordic nao encontrado em {NORDIC}\n"
               f"       veja segment-center-signal/ORIGEM.md")
    fonte = open(NORDIC, encoding="utf-8").read()
    if MARCADOR not in fonte:
        morrer(f"marcador {MARCADOR!r} nao encontrado em {NORDIC}.\n"
               f"       o arquivo mudou; ajuste MARCADOR neste script")
    ns = {}
    exec(compile(fonte[: fonte.index(MARCADOR)], NORDIC, "exec"), ns)
    for f in ("prepare_data", "segment_data", "create_segmented_df", "remove_nrows"):
        if f not in ns:
            morrer(f"funcao {f}() nao encontrada no script da Nordic")
    return ns


def le_classe(caminho, pd):
    """Le um CSV do prep_dataset.py e valida header e classe unica."""
    df = pd.read_csv(caminho, on_bad_lines="skip")
    if list(df.columns) != COLUNAS_LAB:
        morrer(f"{caminho}: header inesperado\n"
               f"       esperado: {','.join(COLUNAS_LAB)}\n"
               f"       lido    : {','.join(map(str, df.columns))}")
    if df.isnull().sum().sum():
        morrer(f"{caminho}: tem valores vazios — o Lab rejeita")
    rotulos = df["class"].unique()
    if len(rotulos) != 1:
        morrer(f"{caminho}: {len(rotulos)} classes no mesmo arquivo; esperava 1")
    return df, int(rotulos[0])


def centros_dos_segmentos(segmentos, n_linhas, janela):
    """Converte os segmentos da Nordic em centros validos.

    Descarta os que estourariam os limites: create_segmented_df() faz df.iloc[i]
    sem checar, e um i negativo NAO da erro — o pandas conta do fim, costurando
    linhas do final da gravacao dentro do segmento, em silencio.
    """
    meia = janela // 2
    bons, descartados = [], 0
    for inicio, fim in segmentos:
        centro = int((inicio + fim) / 2)
        if centro - meia < 0 or centro + meia > n_linhas:
            descartados += 1
            continue
        bons.append(centro)
    return bons, descartados


def pontua(centros, vetor, janela):
    """Mede onde o pico cai dentro de cada janela. Centro ideal = janela/2."""
    meia = janela // 2
    picos = []
    for c in centros:
        trecho = vetor[c - meia : c + meia]
        picos.append(max(range(len(trecho)), key=lambda k: abs(trecho[k])))
    if not picos:
        return None
    lo, hi = 0.4 * janela, 0.6 * janela
    return {
        "n": len(picos),
        "mediana": st.median(picos),
        "desvio": st.pstdev(picos) if len(picos) > 1 else 0.0,
        "centro": sum(1 for p in picos if lo <= p < hi) / len(picos),
        "pontas": sum(1 for p in picos if p < 0.25 * janela or p >= 0.75 * janela) / len(picos),
    }


def varre(ns, df, janela, eixos, coefs, np):
    """Varre (eixo, coef) e devolve todos os resultados pontuados.

    prepare_data() nao depende do coef, entao o envelope e calculado uma vez por
    eixo e a varredura de coef reaproveita — e o que torna isto rapido.
    """
    work_wind = int(janela * 0.95)
    resultados = []
    for eixo in eixos:
        col = LAB_PARA_NORDIC[eixo]
        vetor = df[col].values.reshape(len(df[col]))
        dados = vetor - np.mean(vetor)
        envelope = ns["prepare_data"](dados, 1, work_wind)
        for coef in coefs:
            ns["config"] = {"work_axis": col, "work_wind_size": work_wind,
                            "total_wind_size": janela, "threshold_coef": coef,
                            "step": 1}
            segmentos = ns["segment_data"](envelope, work_wind, coef)
            centros, descartados = centros_dos_segmentos(segmentos, len(df), janela)
            p = pontua(centros, vetor, janela)
            if p is None or p["n"] < MIN_GESTOS:
                resultados.append({"eixo": eixo, "coef": coef, "n": p["n"] if p else 0,
                                   "valido": False})
                continue
            resultados.append({"eixo": eixo, "coef": coef, "valido": True,
                               "descartados": descartados, **p})
    return resultados


def melhor(resultados):
    """Maior NUMERO ABSOLUTO de gestos bem centrados. Empate: menor desvio.

    Deliberadamente nao e a FRACAO centrada: essa metrica se ganha jogando dado
    fora. Subir o limiar descarta os gestos mais fracos, que sao justamente os
    piores de centralizar, entao a fracao sobe enquanto a amostragem encolhe.
    Medido no swipe_right: gyro_x/1.30 da 88.1% centrados mas so 59 gestos (de
    135), enquanto gyro_y/0.95 da 71.1% de 135 — 96 gestos bem centrados contra
    52. O produto n * centro escolhe o segundo, que e o certo.
    """
    validos = [r for r in resultados if r["valido"]]
    if not validos:
        return None
    return max(validos, key=lambda r: (round(r["n"] * r["centro"], 1), -r["desvio"]))


def imprime_varredura(resultados, escolhido, janela):
    print(f"\n  calibracao (janela {janela}, centro ideal = {janela // 2})")
    print(f"  {'eixo':9} {'coef':>5} {'gestos':>7} {'mediana':>8} {'desvio':>7} "
          f"{'centro':>7} {'pontas':>7}")
    eixo_atual = None
    for r in resultados:
        if not r["valido"]:
            continue
        if r["eixo"] != eixo_atual:
            eixo_atual = r["eixo"]
        marca = "  <--" if r is escolhido else ""
        print(f"  {r['eixo']:9} {r['coef']:5.2f} {r['n']:7} {r['mediana']:8.0f} "
              f"{r['desvio']:7.1f} {100*r['centro']:6.1f}% {100*r['pontas']:6.1f}%{marca}")


def processa_discreto(caminho, args, ns, pd, np):
    df, rotulo = le_classe(caminho, pd)
    linhas_brutas = len(df)
    df.columns = COLUNAS_NORDIC
    df = ns["remove_nrows"](df, args.trim, first=True)
    df = ns["remove_nrows"](df, args.trim, first=False)
    df.reset_index(drop=True, inplace=True)

    eixos = EIXOS_CANDIDATOS if args.axis == "auto" else [args.axis]
    coefs = GRADE_COEF if args.coef == "auto" else [float(args.coef)]

    print(f"\n  arquivo   {caminho}")
    print(f"  classe    {rotulo}")
    print(f"  linhas    {linhas_brutas} brutas -> {len(df)} apos aparar {args.trim} de cada ponta")

    resultados = varre(ns, df, args.window, eixos, coefs, np)
    esc = melhor(resultados)
    if esc is None:
        morrer(f"{caminho}: nenhuma combinacao produziu >= {MIN_GESTOS} gestos.\n"
               f"       confira o eixo, ou se este arquivo e mesmo de gesto discreto")
    imprime_varredura(resultados, esc, args.window)

    # Recorte definitivo, uma unica vez, com a combinacao vencedora.
    col = LAB_PARA_NORDIC[esc["eixo"]]
    ns["config"] = {"work_axis": col, "work_wind_size": int(args.window * 0.95),
                    "total_wind_size": args.window, "threshold_coef": esc["coef"],
                    "step": 1}
    vetor = df[col].values.reshape(len(df[col]))
    envelope = ns["prepare_data"](vetor - np.mean(vetor), 1, int(args.window * 0.95))
    segmentos = ns["segment_data"](envelope, int(args.window * 0.95), esc["coef"])
    centros, descartados = centros_dos_segmentos(segmentos, len(df), args.window)
    segmentos_seguros = [(c - args.window // 2, c + args.window // 2) for c in centros]

    seg = ns["create_segmented_df"](df, segmentos_seguros, args.window)
    seg.columns = COLUNAS_LAB

    # O nome vem do ROTULO, nao do nome do arquivo: "swipe_right_<data>.csv"
    # partido no "_" daria "swipe", e o swipe_left sobrescreveria o swipe_right
    # em silencio.
    os.makedirs(args.out, exist_ok=True)
    saida = os.path.join(args.out, f"{NOME_POR_ROTULO[rotulo]}.csv")
    seg.to_csv(saida, index=False)

    n = len(seg)
    print(f"\n  escolhido eixo {esc['eixo']} · coef {esc['coef']:.2f}")
    print(f"  gravado   {n} linhas ({n // args.window} gestos) -> {saida}")
    if descartados:
        print(f"  nota      {descartados} segmento(s) descartado(s) por cair fora dos limites")
    assert n % args.window == 0, "saida nao e multipla da janela"
    return saida


def processa_continuo(caminho, args, pd):
    df, rotulo = le_classe(caminho, pd)
    n = len(df) - len(df) % args.window
    if n < args.window:
        morrer(f"{caminho}: {len(df)} linhas, menos que uma janela de {args.window}")
    os.makedirs(args.out, exist_ok=True)
    saida = os.path.join(args.out, os.path.basename(caminho))
    df.iloc[:n].to_csv(saida, index=False)
    print(f"  {caminho}  classe {rotulo}: {len(df)} -> {n} linhas "
          f"({n // args.window} janelas) -> {saida}")
    return saida


def main():
    p = argparse.ArgumentParser(
        description="Centraliza gestos discretos, calibrando eixo e limiar por medicao.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="O algoritmo vem de tools/segment-center-signal/ (Nordic). "
               "Ver ORIGEM.md daquela pasta.")
    p.add_argument("entradas", nargs="+",
                   help="CSVs do prep_dataset.py (aceita glob)")
    p.add_argument("-w", "--window", type=int, default=100,
                   help="janela em linhas; PAR, e igual ao Window size do Lab (padrao 100)")
    p.add_argument("--axis", default="auto",
                   help=f"eixo de deteccao: auto ou um de {', '.join(EIXOS_CANDIDATOS)}")
    p.add_argument("--coef", default="auto",
                   help="threshold_coef: auto (varredura) ou um valor fixo")
    p.add_argument("--trim", type=int, default=400,
                   help="linhas descartadas de cada ponta (padrao 400, ~5 s)")
    p.add_argument("--out", default=os.path.join(BASE, "dataset_centered"),
                   help="pasta de saida (padrao 03_central_uart/dataset_centered)")
    p.add_argument("--continuo", action="store_true",
                   help="classe continua (idle, unknown): so apara para multiplo da janela")
    args = p.parse_args()

    if args.window % 2:
        morrer(f"--window {args.window} e impar. O recorte da Nordic e "
               f"range(centro - int(w/2), centro + int(w/2)), que produziria "
               f"{2 * (args.window // 2)} linhas por segmento, nao {args.window}.")
    if args.axis != "auto" and args.axis not in EIXOS_CANDIDATOS:
        morrer(f"--axis {args.axis!r}: use auto ou um de {', '.join(EIXOS_CANDIDATOS)}")

    try:
        import numpy as np
        import pandas as pd
    except ImportError as e:
        morrer(f"falta dependencia: {e.name}. Rode:\n"
               f"       pip install -r tools/segment-center-signal/requirements.txt")

    arquivos = []
    for padrao in args.entradas:
        achados = sorted(glob.glob(padrao))
        if not achados:
            morrer(f"nada casou com {padrao!r}")
        arquivos.extend(achados)

    if args.continuo:
        print(f"\n  aparando {len(arquivos)} arquivo(s) para multiplo de {args.window}\n")
        for caminho in arquivos:
            processa_continuo(caminho, args, pd)
    else:
        ns = carrega_funcoes_nordic()
        for caminho in arquivos:
            processa_discreto(caminho, args, ns, pd, np)

    print(f"\n  Proximo: junte tudo com")
    print(f"    python tools/prep_dataset.py merge \"{args.out}/*.csv\" --out dataset_centrado.csv")
    print(f"  No Lab: window {args.window}, training shift {args.window}, inference shift 33.\n")


if __name__ == "__main__":
    main()
