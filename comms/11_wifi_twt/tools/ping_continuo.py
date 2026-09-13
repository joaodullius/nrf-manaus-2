"""Com sono de mais de um minuto, um ping insistente acaba passando?

A pergunta que fecha a Parte A: com listen interval 600 (~72 s de sono), o
downlink esta MORTO ou apenas raro? Um ping por segundo, sem parar, por 4
minutos — varias janelas de despertar — registrando quais voltaram e quando.

O resultado da bancada: **1 resposta em 481 pings**, aos 237,6 s, com RTT de
20 ms. O enlace nao esta quebrado; a janela e que e minuscula. O radio fica
acordado ~27,5 ms a cada 72 s (0,04% do tempo).

uso:
    python ping_continuo.py --shell COM21 --ppk2 COM3 --jlink 1051898754 \
        --ssid "MinhaRede" --senha "..." --saida ping_li600.json --li 600
"""

import json
import sys
import time

import bancada as b


def main():
    a = b.argumentos(__doc__.splitlines()[0],
                     (("--li",), {"type": int, "default": 600,
                                  "help": "listen interval (padrao: 600)"}),
                     (("--duracao",), {"type": int, "default": 240,
                                       "help": "segundos de ping continuo (padrao: 240)"}))

    ppk = b.abre_ppk2(a.ppk2)
    sh = b.abre_shell(a.shell)

    b.reseta(a.jlink, espera=10)
    if not b.conecta(sh, a.ssid, a.senha, banda="2", listen_interval=a.li, espera=13):
        print("NAO associou")
        return 1
    b.comando(sh, "wifi ps on", 1.5)
    b.comando(sh, "wifi ps_wakeup_mode listen_interval", 1.5)
    ip = b.ip_do_kit(sh)
    if not ip:
        print("associou mas nao pegou IP")
        return 1
    print(f"LI {a.li}, ip {ip}. Ping 1/s por {a.duracao} s...", flush=True)
    time.sleep(4)

    resultados, t0 = [], time.time()
    while time.time() - t0 < a.duracao:
        t = round(time.time() - t0, 1)
        # timeout curto de proposito: o objetivo e contar ACERTOS da janela,
        # nao esperar o proximo despertar.
        v = b.um_ping(ip, timeout_ms=900)
        resultados.append({"t_s": t, "rtt_ms": v})
        if v is not None:
            print(f"   t={t:>6.1f}s  RESPONDEU {v} ms", flush=True)
        time.sleep(0.1)

    ok = [r for r in resultados if r["rtt_ms"] is not None]
    print(f"\n{len(ok)} de {len(resultados)} pings responderam", flush=True)
    if len(ok) > 1:
        ts = [r["t_s"] for r in ok]
        print("instantes:", ts, flush=True)
        print("intervalos entre respostas:",
              [round(ts[i + 1] - ts[i], 1) for i in range(len(ts) - 1)], flush=True)

    sh.close()
    json.dump({"li": a.li, "resultados": resultados}, open(a.saida, "w"), indent=1)
    print("\nsalvo em", a.saida)
    return 0


if __name__ == "__main__":
    sys.exit(main())
