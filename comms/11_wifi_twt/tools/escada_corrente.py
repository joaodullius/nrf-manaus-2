"""Parte A, Passo 2 — a escada de economia de energia medida por CORRENTE.

Percorre os regimes com o firmware do **lab 6** (o shell) e mede cada um por 22 s
com o PPK2 em amperimetro no P10 da EB II:

    sem conectar · ps off · PS+DTIM · PS+listen interval (padrao) · PS+LI 30
    nas duas bandas (2,4 e 5 GHz), onde a banda faz diferenca

A ORDEM do script e o que ele tem de mais importante: estabelecer o caminho do
PPK2 (amperimetro + chave FECHADA) **antes** de resetar a DK. Se a DK bootar com
o companion sem VBAT, o driver desiste dele e o shell responde
"RPU is unresponsive for 10 sec" a tudo.

uso:
    python escada_corrente.py --shell COM21 --ppk2 COM3 --jlink 1051898754 \
        --ssid "MinhaRede" --senha "..." --saida escada_psm.json
"""

import json
import sys
import time

import bancada as b

DURACAO = 22        # s por regime


def main():
    a = b.argumentos(__doc__.splitlines()[0])

    print("1) PPK2")
    ppk = b.abre_ppk2(a.ppk2)

    print("2) reset da LM20-DK (com o companion ja alimentado)")
    b.reseta(a.jlink, espera=8)
    sh = b.abre_shell(a.shell)

    print("3) scan de verificacao")
    s = b.comando(sh, "wifi scan", 12)
    if "Scan request done" not in s:
        print("   !! o radio nao respondeu ao scan -- abortando")
        print(s[-400:])
        return 1
    print("   ok, radio vivo")

    cenarios = []

    def anota(id_, rotulo, banda, link, amostras):
        r = b.resumo(amostras)
        cenarios.append({"id": id_, "rotulo": rotulo, "banda": banda, "link": link,
                         "resumo": r, "amostras": amostras[::b.DECIMACAO]})
        print(f"   {id_:<5} {rotulo:<26} media {r['media_uA']/1000:8.3f} mA"
              f"   p50 {r['p50_uA']/1000:7.3f}   max {r['max_uA']/1000:7.2f}")

    print("\n== A. sem conectar (linha de base do radio ocioso)")
    anota("A", "Sem conectar", "-", {}, b.mede(ppk, DURACAO))

    for banda, nome in (("2", "2,4 GHz"), ("5", "5 GHz")):
        print(f"\n== {nome}")
        if not b.conecta(sh, a.ssid, a.senha, banda=banda, espera=10):
            print(f"   !! nao conectou em {nome}")
            continue
        link = b.estado_do_link(sh)
        print(f"   link: canal {link['canal']}, RSSI {link['rssi']}, "
              f"DTIM {link['dtim']}, beacon {link['beacon_ms']} ms")

        b.comando(sh, "wifi ps off", 1.5)
        time.sleep(3)
        anota(f"B{banda}", f"{nome} · ps OFF", nome, link, b.mede(ppk, DURACAO))

        b.comando(sh, "wifi ps on", 1.5)
        b.comando(sh, "wifi ps_wakeup_mode dtim", 1.5)
        time.sleep(3)
        anota(f"C{banda}", f"{nome} · PS · DTIM", nome, link, b.mede(ppk, DURACAO))

        b.comando(sh, "wifi ps_wakeup_mode listen_interval", 1.5)
        time.sleep(3)
        anota(f"D{banda}", f"{nome} · PS · LI padrao", nome, link, b.mede(ppk, DURACAO))

    # LI 30 exige RECONECTAR: o valor viaja no quadro de associacao.
    print("\n== 2,4 GHz com listen interval 30")
    b.comando(sh, "wifi disconnect", 2.0)
    time.sleep(3)
    if b.conecta(sh, a.ssid, a.senha, banda="2", listen_interval=30, espera=10):
        link = b.estado_do_link(sh)
        print(f"   link: canal {link['canal']}, DTIM {link['dtim']}")
        b.comando(sh, "wifi ps on", 1.5)
        b.comando(sh, "wifi ps_wakeup_mode listen_interval", 1.5)
        time.sleep(3)
        anota("E2", "2,4 GHz · PS · LI 30", "2,4 GHz", link, b.mede(ppk, DURACAO))
        # Conferir SEMPRE: errar o nome do comando nao devolve erro, e o valor
        # antigo continua valendo.
        print("   ", " | ".join(l.strip() for l in b.comando(sh, "wifi ps", 1.5).splitlines()
                                if "PS " in l or "listen" in l.lower()))
    else:
        print("   !! nao conectou com LI 30 (o AP pode ter recusado)")

    ppk.stop_measuring()
    sh.close()
    json.dump(cenarios, open(a.saida, "w"), indent=1)
    print("\nsalvo em", a.saida)
    return 0


if __name__ == "__main__":
    sys.exit(main())
