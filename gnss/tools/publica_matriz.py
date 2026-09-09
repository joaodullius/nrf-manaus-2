# -*- coding: utf-8 -*-
"""Prepara as capturas da matriz para irem ao repositorio.

Faz duas coisas que o log cru nao entrega:

1. Fatia o fluxo do nRF9151 nas MESMAS janelas dos blocos do X20P, gerando um
   arquivo por bloco. E o que torna o par comparavel: cada bloco do X20P passa a
   ter ao lado o mesmo intervalo de tempo visto pelo outro receptor.

2. Gera o .uc2 de cada arquivo, que e o formato que o u-center 2 abre. Sem ele o
   log so serve para o Python; com ele da para reproduzir a captura na
   ferramenta da u-blox e conferir o mapa de desvio contra o nosso.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "C:/work/nrf-manaus-2/gnss/tools")
import uc2

ORIGEM = Path("C:/b/matriz")
DESTINO = Path("C:/work/nrf-manaus-2/gnss/capturas/matriz")


def registros_de(linhas_com_tempo):
    """(tempo_unix, bytes) -> Registro com ts em ms desde o inicio."""
    t0 = linhas_com_tempo[0][0]
    return [uc2.Registro(int((t - t0) * 1000), d) for t, d in linhas_com_tempo]


def fatia_9151(ini, fim):
    saida = []
    with open(ORIGEM / "ref_9151.tsv", encoding="utf-8", errors="replace") as f:
        for ln in f:
            t, _, sent = ln.partition("\t")
            try:
                t = float(t)
            except ValueError:
                continue
            if ini <= t <= fim:
                saida.append((t, sent.strip().encode("ascii", "replace") + b"\r\n"))
    return saida


janelas = json.load(open(ORIGEM / "_janelas.json"))
for j in janelas:
    nome = j["bloco"]

    # nRF9151: a mesma janela, vista pelo outro receptor
    par = fatia_9151(j["ini"], j["fim"])
    if par:
        alvo = DESTINO / ("9151_" + nome + ".nmea")
        alvo.write_bytes(b"".join(d for _, d in par))
        uc2.escrever(alvo.with_suffix(".uc2"), registros_de(par),
                     device_name="COM23",
                     start_time=datetime.fromtimestamp(par[0][0], timezone.utc))

    # X20P: o log cru vira .uc2 mantendo o ritmo real das sentencas
    cru = (ORIGEM / (nome + ".nmea")).read_bytes()
    if not cru:
        continue
    linhas = [l + b"\r\n" for l in cru.split(b"\r\n") if l]
    passo = (j["fim"] - j["ini"]) / max(len(linhas), 1)
    regs = [uc2.Registro(int(i * passo * 1000), l) for i, l in enumerate(linhas)]
    uc2.escrever(DESTINO / (nome + ".uc2"), regs, device_name="COM17",
                 start_time=datetime.fromtimestamp(j["ini"], timezone.utc))
    print("%s  X20P %d sentencas  |  nRF9151 %d sentencas"
          % (nome, len(linhas), len(par)))
