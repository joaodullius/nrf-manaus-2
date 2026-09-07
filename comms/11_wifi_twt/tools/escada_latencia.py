"""Parte A, Passo 1 — a mesma escada medida por LATENCIA, sem instrumento.

Cada regime e medido com pings ISOLADOS. Duas armadilhas que este script existe
para evitar, e as duas foram pagas na bancada:

1. **Rajada nao mede nada.** O nRF70 tem dynamic power save com timer de
   inatividade de 100 ms: depois do primeiro pacote o radio fica acordado, e
   `ping -n 20` mede ~8 ms em qualquer regime.
2. **O espacamento pode bater com o ciclo de dormida.** A primeira medida do
   listen interval 30 usou pings de 3 em 3 s contra um ciclo de ~2,7 s e deu
   mediana de 53 ms — aliasing, nao latencia. Por isso a pausa aqui e
   ALEATORIA e sempre bem maior que o sono do regime.

O PPK2 nao mede nada neste script, mas precisa ser aberto assim mesmo: com o SB10
cortado ele esta no caminho do VBAT, e a chave dele fica ABERTA enquanto ninguem
a fecha.

uso:
    python escada_latencia.py --shell COM21 --ppk2 COM3 --jlink 1051898754 \
        --ssid "MinhaRede" --senha "..." --saida latencia_psm.json
"""

import json
import random
import sys
import time

import bancada as b

N_PINGS = 12


def main():
    a = b.argumentos(__doc__.splitlines()[0])

    ppk = b.abre_ppk2(a.ppk2)          # so para fechar a chave; fica vivo ate o fim
    b.reseta(a.jlink, espera=9)
    sh = b.abre_shell(a.shell)

    saida = []

    def cenario(nome, ip, pausa_min, pausa_max):
        """`pausa_min` tem de ser maior que o ciclo de sono do regime, ou a
        medida vira batimento entre dois periodos."""
        rtts, perdidos = [], 0
        for _ in range(N_PINGS):
            time.sleep(random.uniform(pausa_min, pausa_max))
            v = b.um_ping(ip, timeout_ms=6000)
            if v is None:
                perdidos += 1
            else:
                rtts.append(v)
        s = sorted(rtts)
        r = ({"n": 0} if not s else
             {"n": len(s), "min": s[0], "mediana": s[len(s) // 2],
              "media": round(sum(s) / len(s), 1), "max": s[-1]})
        saida.append({"regime": nome, "rtts_ms": rtts, "sem_resposta": perdidos,
                      "pausa_s": [pausa_min, pausa_max], "resumo": r})
        print(f"   {nome:<36} n={r['n']:<3} min {r.get('min','-'):>4} "
              f"mediana {r.get('mediana','-'):>5} max {r.get('max','-'):>5} ms"
              f"   sem resposta: {perdidos}")

    print("conectando em 2,4 GHz com listen interval 10")
    if not b.conecta(sh, a.ssid, a.senha, banda="2", listen_interval=10):
        print("!! nao conectou")
        return 1
    ip = b.ip_do_kit(sh)
    print("   IP do kit:", ip)
    if not ip:
        print("!! associou mas nao pegou IP")
        return 1

    print("\n== escada de latencia (um ping isolado por vez)")
    b.comando(sh, "wifi ps off", 1.5)
    time.sleep(3)
    cenario("PS desligado", ip, 3.0, 4.0)

    b.comando(sh, "wifi ps on", 1.5)
    b.comando(sh, "wifi ps_wakeup_mode dtim", 1.5)
    time.sleep(3)
    cenario("PS · DTIM (3 x 100 ms = 300 ms)", ip, 3.0, 4.0)

    b.comando(sh, "wifi ps_wakeup_mode listen_interval", 1.5)
    time.sleep(3)
    cenario("PS · listen interval 10 (~900 ms)", ip, 3.0, 4.5)

    print("\nreconectando com listen interval 30 (~2,7 s de sono)")
    b.comando(sh, "wifi disconnect", 2.0)
    time.sleep(3)
    if b.conecta(sh, a.ssid, a.senha, banda="2", listen_interval=30):
        ip = b.ip_do_kit(sh) or ip
        b.comando(sh, "wifi ps on", 1.5)
        b.comando(sh, "wifi ps_wakeup_mode listen_interval", 1.5)
        time.sleep(3)
        cenario("PS · listen interval 30 (~2,7 s)", ip, 7.0, 12.0)
    else:
        print("   !! nao conectou com LI 30")

    sh.close()
    json.dump(saida, open(a.saida, "w"), indent=1)
    print("\nsalvo em", a.saida)
    return 0


if __name__ == "__main__":
    sys.exit(main())
