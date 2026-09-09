# -*- coding: utf-8 -*-
"""Le a matriz e devolve CEP50/CEP95 por bloco e por condicao.

Cada bloco vira um CEP proprio, calculado dentro da sua janela de 5 min. O que
se compara entre condicoes e a MEDIANA das tres rodadas, nunca o CEP de tudo
concatenado: entre um bloco e outro o ambiente deriva, e essa deriva entra como
dispersao, inflando o numero e as vezes invertendo o resultado.

O nRF9151 e fatiado exatamente nas mesmas janelas do X20P, entao cada linha da
tabela tem sua propria referencia simultanea.
"""
import json
import statistics
import sys

sys.path.insert(0, "C:/work/nrf-manaus-2/gnss/tools")
import nmea

SAIDA = "C:/b/matriz"
NOMES = {"A": "sem GLONASS, sem NTRIP", "B": "com GLONASS, sem NTRIP",
         "C": "sem GLONASS, com NTRIP", "D": "com GLONASS, com NTRIP"}


def fatia_9151(ini, fim):
    """Le o fluxo carimbado e devolve so as sentencas dentro da janela."""
    linhas = []
    with open(SAIDA + "/ref_9151.tsv", encoding="utf-8", errors="replace") as f:
        for ln in f:
            t, _, sent = ln.partition("\t")
            try:
                t = float(t)
            except ValueError:
                continue
            if ini <= t <= fim:
                linhas.append(sent.strip())
    return nmea.ler_fluxo("\r\n".join(linhas).encode("ascii", "replace"))


def sats_usados(caminho):
    """Media de satelites usados por epoca, contados nos GSA.

    O campo numSV da GGA nao serve para isso: o NMEA 0183 o limita a 12, e com
    multiconstelacao ele fica cravado em 12 tanto com GLONASS quanto sem. Quem
    tem o numero de verdade e a GSA, que lista os PRN efetivamente usados — uma
    sentenca por constelacao, ate 12 PRN em cada.
    """
    usados = epocas = 0
    with open(caminho, "rb") as f:
        for ln in f.read().split(b"\r\n"):
            if ln[3:6] == b"GSA":
                c = ln.split(b",")
                usados += sum(1 for x in c[3:15] if x.strip())
            elif ln[3:6] == b"GGA":
                epocas += 1
    return usados / epocas if epocas else None


def painel(fixes):
    """CEP do bloco inteiro, e tambem so das epocas em RTK fixo.

    O bloco inteiro e o que o usuario recebe de fato; o recorte em qualidade 4
    diz de quanto o RTK e capaz quando esta resolvido. Se um bloco de NTRIP
    passou metade do tempo em flutuante, os dois numeros ficam bem diferentes —
    e e essa diferenca que conta a historia, nao a media dos dois.
    """
    if not fixes:
        return None
    e = nmea.estatisticas(fixes)
    p = {"n": e["n"],
         "cep50": e["hpe_m"]["cep50"],
         "cep95": e["hpe_m"]["cep95"],
         "qual": e["qualidades"],
         "sats": e["sats"]["avg"] if e["sats"] else None,
         "cep50_fixo": None, "cep95_fixo": None, "n_fixo": 0}
    fixos = [f for f in fixes if f.qualidade == 4]
    p["n_fixo"] = len(fixos)
    if len(fixos) >= 30:
        ef = nmea.estatisticas(fixos)
        p["cep50_fixo"] = ef["hpe_m"]["cep50"]
        p["cep95_fixo"] = ef["hpe_m"]["cep95"]
    return p


def linha(rot, p):
    if not p:
        return "  %-26s  (sem dados)" % rot
    q = " ".join("%s=%d" % (k, v) for k, v in p["qual"].items())
    s = "  %-26s  n=%4d  CEP50=%6.3f  CEP95=%6.3f  sats=%4.1f  %s" % (
        rot, p["n"], p["cep50"], p["cep95"], p["sats"] or 0, q)
    if p["cep50_fixo"] is not None:
        s += "\n  %-26s  n=%4d  CEP50=%6.3f  CEP95=%6.3f   (so RTK fixo)" % (
            "", p["n_fixo"], p["cep50_fixo"], p["cep95_fixo"])
    return s


def relatorio():
    janelas = json.load(open(SAIDA + "/_janelas.json"))
    por_cond = {}
    por_cond_9151 = []

    print("=" * 96)
    print("BLOCO A BLOCO  (cada CEP dentro da sua janela de 5 min)")
    print("=" * 96)
    for j in janelas:
        arq = SAIDA + "/" + j["bloco"] + ".nmea"
        fx = nmea.ler_arquivo(arq)
        px = painel(fx)
        if px:
            px["sats"] = sats_usados(arq)
        p9 = painel(fatia_9151(j["ini"], j["fim"]))
        print("%s  %s" % (j["bloco"], NOMES[j["cond"]]))
        print(linha("X20P", px))
        print(linha("nRF9151 (simultaneo)", p9))
        if px:
            por_cond.setdefault(j["cond"], []).append(px)
        if p9:
            por_cond_9151.append(p9)

    print()
    print("=" * 96)
    print("POR CONDICAO  (mediana das rodadas; a faixa e min-max)")
    print("=" * 96)
    print("  %-26s  %-22s  %-22s" % ("condicao", "CEP50 [m]", "CEP95 [m]"))
    for cd in "ABCD":
        ps = por_cond.get(cd)
        if not ps:
            continue
        c50 = [p["cep50"] for p in ps]
        c95 = [p["cep95"] for p in ps]
        print("  %-26s  %6.3f  (%.3f-%.3f)   %6.3f  (%.3f-%.3f)" % (
            NOMES[cd], statistics.median(c50), min(c50), max(c50),
            statistics.median(c95), min(c95), max(c95)))
    if por_cond_9151:
        c50 = [p["cep50"] for p in por_cond_9151]
        c95 = [p["cep95"] for p in por_cond_9151]
        print("  %-26s  %6.3f  (%.3f-%.3f)   %6.3f  (%.3f-%.3f)" % (
            "nRF9151 (GPS L1)", statistics.median(c50), min(c50), max(c50),
            statistics.median(c95), min(c95), max(c95)))

    print()
    print("=" * 96)
    print("EFEITOS ISOLADOS  (razao de medianas; cada efeito com o outro fator fixo)")
    print("=" * 96)


    def med(cd, chave):
        ps = por_cond.get(cd)
        return statistics.median([p[chave] for p in ps]) if ps else None


    for chave in ("cep50", "cep95"):
        print("  %s:" % chave.upper())
        for rot, a, b in (("GLONASS sem NTRIP  (A -> B)", "A", "B"),
                          ("GLONASS com NTRIP  (C -> D)", "C", "D"),
                          ("NTRIP sem GLONASS  (A -> C)", "A", "C"),
                          ("NTRIP com GLONASS  (B -> D)", "B", "D")):
            x, y = med(a, chave), med(b, chave)
            if x and y:
                print("    %-28s  %6.3f -> %6.3f   %5.2fx" % (rot, x, y, x / y))


if __name__ == "__main__":
    relatorio()
