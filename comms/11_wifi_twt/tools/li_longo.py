"""Listen interval LONGO — o degrau que chega ao patamar do TWT.

Mede corrente com sono de ~10 s, ~30 s e ~72 s, que e a faixa em que o listen
interval pode ser comparado com o TWT de 1 minuto do datasheet. Para cada valor,
alem da media, segmenta os despertares (duracao, periodo, carga) e tenta **um
ping** com timeout longo, para registrar se o downlink ainda existe.

O listen interval e contado em BEACONS (100 ms), arredondado para o multiplo do
DTIM (3 nesta bancada):

    LI 100 -> ~10 s      LI 300 -> ~30 s      LI 600 -> ~72 s

uso:
    python li_longo.py --shell COM21 --ppk2 COM3 --jlink 1051898754 \
        --ssid "MinhaRede" --senha "..." --saida li_longo.json
"""

import json
import sys
import time

import bancada as b

# (listen interval, segundos de captura) — a captura tem de cobrir varios ciclos
REGIMES = ((100, 150), (300, 240), (600, 360))


def main():
    a = b.argumentos(__doc__.splitlines()[0])

    ppk = b.abre_ppk2(a.ppk2)
    sh = b.abre_shell(a.shell)

    saida = []
    for li, duracao in REGIMES:
        print(f"== LI {li}", flush=True)
        b.reseta(a.jlink, espera=10)
        if not b.conecta(sh, a.ssid, a.senha, banda="2", listen_interval=li, espera=13):
            print("   NAO associou", flush=True)
            saida.append({"li": li, "associou": False})
            continue

        b.comando(sh, "wifi ps on", 1.5)
        b.comando(sh, "wifi ps_wakeup_mode listen_interval", 1.5)
        ip = b.ip_do_kit(sh)
        time.sleep(4)

        print(f"   medindo {duracao}s (ip {ip})", flush=True)
        amostras = b.mede(ppk, duracao)
        dec = amostras[::b.DECIMACAO]
        ev = b.pulsos(dec)
        n = len(ev)
        janela_s = len(dec) / (b.TAXA_PPK2 / b.DECIMACAO)
        media = sum(amostras) / len(amostras)

        # Depois da captura: o kit continua associado? E responde?
        ainda = "COMPLETED" in b.comando(sh, "wifi status", 2.0)
        ping = b.um_ping(ip, timeout_ms=90000) if ip else None

        r = {"li": li, "associou": True, "dur_s": duracao,
             "media_uA": round(media, 1), "despertares": n,
             "periodo_s": round(janela_s / n, 2) if n else None,
             "dur_pulso_ms": round(sum(e[0] for e in ev) / n, 1) if n else None,
             "carga_uC": round(sum(e[1] for e in ev) / n) if n else None,
             "ainda_associado": ainda, "ping_ms": ping if ping is not None else "timeout",
             "amostras": [round(v, 1) for v in dec[:40000]]}
        saida.append(r)
        print(f"   media {media:.0f} uA | {n} desp. em {janela_s:.0f}s "
              f"| periodo {r['periodo_s']}s | pulso {r['dur_pulso_ms']}ms "
              f"| carga {r['carga_uC']} uC | assoc={ainda} | ping={r['ping_ms']}",
              flush=True)

    sh.close()
    json.dump(saida, open(a.saida, "w"), indent=1)
    print("\nsalvo em", a.saida)
    return 0


if __name__ == "__main__":
    sys.exit(main())
