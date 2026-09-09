# -*- coding: utf-8 -*-
"""Le a campanha de ceu aberto e devolve dispersao por condicao.

Quatro linhas, todas em blocos de 300 s medidos ao mesmo tempo:

    nRF9151                 GPS L1, antena ao lado do rover
    X20P autonomo           todas as constelacoes, sem correcao
    X20P + rede             correcao NTRIP, estacao a 16,4 km
    X20P + base local       a outra unidade a 1,42 m

Regras que valem para todas, e cada uma custou uma medida errada nesta bancada:

* **So o regime dominante conta.** Um bloco que mistura qualidades nao mede o
  ruido de nenhuma delas: mede o DEGRAU entre as solucoes, que ja apareceu 7x
  maior que o ruido. Cada bloco e recortado na qualidade que o define.
* **O SBAS e recortado fora do autonomo.** Ele entra e sai sozinho (7 epocas num
  bloco, 49 no outro) e ja fabricou um efeito de constelacao que nao existia.
* **Nunca concatenar blocos.** Entre blocos o ambiente deriva, e a deriva entra
  como dispersao. Cada bloco rende um CEP; compara-se a mediana dos blocos.
* **O nRF9151 e fatiado nas MESMAS janelas.** Ele e a testemunha: quando varia
  junto com o X20P, a variacao e do ceu; quando nao, e do receptor.
"""
import json
import statistics
import sys
from collections import Counter

sys.path.insert(0, "C:/work/nrf-manaus-2/gnss/tools")
import nmea

SAIDA = "C:/b/ceu2"
QUAL_DA_COND = {"A": 1, "V": 4, "L": 4}     # regime que define cada condicao
NOMES = {"A": "X20P autônomo", "V": "X20P + rede (16,4 km)",
         "L": "X20P + base local (1,42 m)"}


def carrega(caminho):
    saida = []
    with open(caminho, encoding="utf-8", errors="replace") as f:
        for ln in f:
            t, _, s = ln.partition("\t")
            try:
                saida.append((float(t), s.strip()))
            except ValueError:
                pass
    return saida


def fatia(dados, ini, fim):
    txt = "\r\n".join(s for t, s in dados if ini <= t <= fim)
    return nmea.ler_fluxo(txt.encode("ascii", "replace"))


def painel(fx):
    if len(fx) < 30:
        return None
    e = nmea.estatisticas(fx)
    return {"n": e["n"], "cep50": e["hpe_m"]["cep50"], "cep95": e["hpe_m"]["cep95"],
            "hdop": e["hdop"]["avg"] if e["hdop"] else None}


def main():
    janelas = json.load(open(SAIDA + "/_janelas.json"))
    rover = carrega(SAIDA + "/rover.tsv")
    ref = carrega(SAIDA + "/ref_9151.tsv")

    por_cond, ref_blocos, tempos = {}, [], {}
    print("=" * 92)
    print("BLOCO A BLOCO")
    print("=" * 92)
    for j in janelas:
        fx = fatia(rover, j["ini"], j["fim"])
        q = Counter(f.qualidade for f in fx)
        alvo = QUAL_DA_COND[j["cond"]]
        sub = [f for f in fx if f.qualidade == alvo]
        p = painel(sub)
        descartado = len(fx) - len(sub)
        f9 = painel(fatia(ref, j["ini"], j["fim"]))

        comp = " ".join("q%d=%d" % (k, v) for k, v in sorted(q.items()))
        print("%-7s %-28s %s" % (j["bloco"], NOMES[j["cond"]], comp))
        if p:
            print("        no regime q%d: n=%3d  CEP50=%.3f  CEP95=%.3f"
                  "  (descartadas %d epocas fora do regime)"
                  % (alvo, p["n"], p["cep50"], p["cep95"], descartado))
            por_cond.setdefault(j["cond"], []).append(p)
        else:
            print("        SEM epocas suficientes em q%d — bloco nao contribui" % alvo)
        if f9:
            print("        nRF9151 simultaneo: n=%3d  CEP50=%.3f  CEP95=%.3f"
                  % (f9["n"], f9["cep50"], f9["cep95"]))
            ref_blocos.append(f9)
        tempos.setdefault(j["cond"], []).append(j["s_ate_regime"])

    print()
    print("=" * 92)
    print("POR CONDICAO — mediana dos blocos, faixa min-max")
    print("=" * 92)
    linhas = [("nRF9151 (GPS L1)", ref_blocos)]
    for c in ("A", "V", "L"):
        if c in por_cond:
            linhas.append((NOMES[c], por_cond[c]))
        else:
            print("  %-30s NENHUM bloco chegou ao regime" % NOMES[c])
    for rot, ps in linhas:
        c50 = [p["cep50"] for p in ps]
        c95 = [p["cep95"] for p in ps]
        print("  %-30s %d blocos  CEP50=%.3f (%.3f-%.3f)  CEP95=%.3f (%.3f-%.3f)"
              % (rot, len(ps), statistics.median(c50), min(c50), max(c50),
                 statistics.median(c95), min(c95), max(c95)))

    print()
    print("=" * 92)
    print("TEMPO ATE O REGIME — o que a linha de base curta compra")
    print("=" * 92)
    for c in ("V", "L"):
        if c in tempos:
            ts = tempos[c]
            fixou = sum(1 for j in janelas
                        if j["cond"] == c and j["s_ate_regime"] < 400)
            print("  %-30s %s   fixou em %d de %d tentativas"
                  % (NOMES[c], ", ".join("%.0f s" % t for t in ts), fixou, len(ts)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
