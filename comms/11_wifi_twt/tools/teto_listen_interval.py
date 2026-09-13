"""Ate onde o listen interval vai — e onde ele para de ser util.

Varre valores de listen interval e, para cada um, registra tres coisas
diferentes que costumam ser confundidas numa so:

    o shell ACEITOU o valor?   (a API do Zephyr aceita 0-65535)
    o AP ASSOCIOU com ele?     (na bancada, associou em todos)
    o kit ainda RESPONDE?      (e aqui que a coisa morre)

A conclusao da bancada foi que **associar nao e ser alcancavel**: o AP aceita
qualquer valor e depois descarta os quadros bufferizados que passam do
MPDU/MSDU lifetime. O limite util fica nas dezenas.

Cada valor exige um RESET e uma reassociacao: o listen interval viaja no quadro
de associacao.

uso:
    python teto_listen_interval.py --shell COM21 --ppk2 COM3 --jlink 1051898754 \
        --ssid "MinhaRede" --senha "..." --saida teto_li.json
    ... --valores 10,50,100,300,1000,10000,65535
"""

import json
import re
import sys
import time

import bancada as b

PADRAO = "10,50,100,300,1000,10000,65535"


def main():
    a = b.argumentos(__doc__.splitlines()[0],
                     (("--valores",), {"default": PADRAO,
                                       "help": f"listen intervals a testar (padrao: {PADRAO})"}))
    valores = [int(v) for v in a.valores.split(",")]

    ppk = b.abre_ppk2(a.ppk2)          # fica vivo ate o fim: chave fechada
    sh = b.abre_shell(a.shell)

    resultados = []
    for li in valores:
        b.reseta(a.jlink, espera=10)
        eco = b.comando(sh, f"wifi ps_listen_interval {li}", 1.5)
        rejeitado = any(t in eco for t in ("rror", "nvalid", "ange"))

        associou = b.conecta(sh, a.ssid, a.senha, banda="2", espera=13)
        lido, ping = "-", None
        if associou:
            b.comando(sh, "wifi ps on", 1.5)
            b.comando(sh, "wifi ps_wakeup_mode listen_interval", 1.5)
            time.sleep(2)
            # Conferir SEMPRE: errar o nome do comando nao devolve erro -- o
            # shell imprime o help e o valor ANTIGO continua valendo.
            m = re.search(r"listen_interval:\s*(\d+)", b.comando(sh, "wifi ps", 1.5))
            lido = m.group(1) if m else "?"
            ip = b.ip_do_kit(sh)
            if ip:
                time.sleep(6)
                ping = b.um_ping(ip, timeout_ms=9000) or "timeout"

        resultados.append({"li_pedido": li, "shell_rejeitou": rejeitado,
                           "associou": associou, "li_reportado": lido,
                           "ping_ms": ping})
        print(f"  LI {li:>6}: shell {'REJEITOU' if rejeitado else 'aceitou':<8} "
              f"associou={'sim' if associou else 'NAO':<3} "
              f"reportado={lido:<6} ping={ping}")

    sh.close()
    json.dump(resultados, open(a.saida, "w"), indent=1)
    print("\nsalvo em", a.saida)
    return 0


if __name__ == "__main__":
    sys.exit(main())
