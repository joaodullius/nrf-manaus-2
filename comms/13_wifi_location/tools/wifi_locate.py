#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ferramenta de PC do lab 13 (wifi_location) -- codigo do curso (nrf-manaus-2).

O kit varre os pontos de acesso Wi-Fi ao redor e manda a lista para o PC por
um socket TCP simples (uma linha "AP,<bssid>,<rssi>,<frequencia_mhz>,<ssid>"
por ponto de acesso, terminada por "FIM"). Esta ferramenta recebe essa lista,
resolve a posicao consultando os Location Services (Wi-Fi) do nRF Cloud e
imprime as duas metades: os APs recebidos e a coordenada resolvida.

O kit nunca sabe onde esta -- so enxerga vizinhos. Quem resolve a posicao e o
banco de dados de mapeamento de APs do nRF Cloud, do lado do PC (por isso o
PC precisa de internet; o kit so precisa da rede local, para falar com esta
ferramenta).

Uso:
    set NRFCLOUD_OAT=oat_...            (Organization Auth Token do nRF Cloud)
    python wifi_locate.py --porta 9000 --org <orgSlug> --proj <projSlug>

Sem --org/--proj, valores desta conta (nao sao segredo -- o segredo e so o
token) servem de padrao; um instrutor com outra conta sobrescreve por
argumento ou pelas variaveis de ambiente NRF_CLOUD_ORG_SLUG/
NRF_CLOUD_PROJECT_SLUG/NRF_CLOUD_TENANT_ID.
"""
from __future__ import annotations

import argparse
import os
import re
import socket
import sys

import requests

ENDPOINT = ("https://api.nrfcloud.com/v1/organizations/{org}/projects/{proj}"
            "/location/wifi")

# Valores desta conta (bancada do curso) -- sobrescrevivel por ambiente ou
# por linha de comando. O segredo e so o token (NRFCLOUD_OAT), nunca estes.
ORG_SLUG_PADRAO = os.environ.get("NRF_CLOUD_ORG_SLUG", "nrfcloud-473f730214ca")
PROJECT_SLUG_PADRAO = os.environ.get("NRF_CLOUD_PROJECT_SLUG", "nrf-project")
TENANT_ID_PADRAO = os.environ.get("NRF_CLOUD_TENANT_ID", "f183b251-25aa-4b61-97b5-473f730214ca")

# Tempo limite de cada conexao HTTP para o nRF Cloud.
TIMEOUT_HTTP_S = 20.0

# Tempo limite de leitura de uma conexao do kit -- um scan inteiro (ate
# ~30 APs) cabe bem dentro disso; acima disso a conexao e dada como morta.
TEMPO_LIMITE_LEITURA_S = 30.0

_LINHA_RE = re.compile(
    r"^AP,([0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5}),(-?\d+),(\d+),(.*)$"
)


def _mac_localmente_administrado(mac: str) -> bool:
    """True se o bit de "endereco administrado localmente" (0x02) do
    primeiro octeto do MAC estiver ligado.

    Um AP real tem BSSID gravado de fabrica (endereco "universalmente
    administrado"); um MAC com esse bit ligado e aleatorio -- geralmente
    aleatorizacao de privacidade do lado cliente, nao o endereco de um AP de
    verdade. O Location Services do nRF Cloud rejeita esses BSSIDs porque
    nao correspondem a nada no banco de dados de mapeamento. Descartar aqui,
    antes de montar a requisicao, evita gastar a chamada paga (o servico e
    cobrado por chamada) so para receber esse erro de volta.
    """
    primeiro_octeto = int(mac.split(":")[0], 16)
    return bool(primeiro_octeto & 0x02)


def parse_scan(linha: str):
    """'AP,<bssid>,<rssi>,<freq>,<ssid>' -> dict do formato do nRF Cloud.

    Devolve None se a linha nao tiver esse formato, o BSSID nao for um MAC
    valido, ou o BSSID for localmente administrado (ver
    `_mac_localmente_administrado`) -- nos tres casos, a linha e descartada
    em vez de propagar um AP inutilizavel.
    """
    m = _LINHA_RE.match(linha.strip("\r\n"))
    if not m:
        return None

    mac, rssi, freq, ssid = m.groups()
    mac = mac.lower()
    if _mac_localmente_administrado(mac):
        return None

    return {
        "macAddress": mac,
        "signalStrength": int(rssi),
        "frequency": int(freq),
        "ssid": ssid,
    }


def montar_requisicao(aps: list) -> dict:
    """{"accessPoints": [...]}; levanta ValueError se houver menos de dois.

    So os campos que o nRF Cloud espera (macAddress, signalStrength) vao no
    corpo -- frequency/ssid, quando presentes em `aps`, servem so para a
    lista impressa no PC (ver `_formatar_ap`) e sao descartados aqui.
    """
    if len(aps) < 2:
        raise ValueError(
            "sao necessarios pelo menos dois pontos de acesso para localizar "
            f"(recebido {len(aps)})"
        )

    return {
        "accessPoints": [
            {"macAddress": ap["macAddress"], "signalStrength": ap["signalStrength"]}
            for ap in aps
        ]
    }


def resolver(aps, org, proj, token, tenant_id=None, timeout=TIMEOUT_HTTP_S):
    """POST no ENDPOINT com Authorization: Bearer <token>.

    Devolve (lat, lon, uncertainty). Levanta ValueError se `aps` tiver menos
    de dois pontos de acesso (via montar_requisicao, antes de gastar a
    chamada cobrada) e RuntimeError se a API responder erro HTTP ou um corpo
    sem lat/lon.
    """
    corpo = montar_requisicao(aps)

    url = ENDPOINT.format(org=org, proj=proj)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "x-nrfcloud-tenantid": tenant_id or TENANT_ID_PADRAO,
    }

    resposta = requests.post(url, headers=headers, json=corpo, timeout=timeout)

    if resposta.status_code != 200:
        raise RuntimeError(
            f"nRF Cloud respondeu HTTP {resposta.status_code} ao resolver a "
            f"posicao: {resposta.text[:300]}"
        )

    try:
        dados = resposta.json()
    except ValueError as exc:
        raise RuntimeError(
            f"resposta do nRF Cloud nao e JSON valido: {resposta.text[:300]}"
        ) from exc

    if not isinstance(dados, dict) or "lat" not in dados or "lon" not in dados:
        raise RuntimeError(f"resposta do nRF Cloud sem lat/lon: {dados}")

    return dados["lat"], dados["lon"], dados.get("uncertainty")


def _receber_scan(conexao: socket.socket) -> list:
    """Le linhas de `conexao` ate 'FIM', devolve os APs que `parse_scan`
    aceitar (linhas invalidas ou com MAC local sao descartadas, nao
    derrubam a conexao)."""
    conexao.settimeout(TEMPO_LIMITE_LEITURA_S)
    buffer = b""
    aps = []

    while True:
        dados = conexao.recv(4096)
        if not dados:
            break
        buffer += dados
        while b"\n" in buffer:
            linha_bruta, buffer = buffer.split(b"\n", 1)
            linha = linha_bruta.decode("utf-8", errors="replace").strip()
            if linha == "FIM":
                return aps
            ap = parse_scan(linha + "\n")
            if ap is not None:
                aps.append(ap)

    return aps


def _formatar_ap(ap: dict) -> str:
    return (f"  {ap['macAddress']}  {ap['signalStrength']:>4} dBm  "
            f"{ap['frequency']:>4} MHz  {ap['ssid']}")


def main():
    parser = argparse.ArgumentParser(description="Ferramenta do lab 13 (wifi_location)")
    parser.add_argument("--porta", type=int, default=9000,
                         help="porta TCP a escutar, esperando o scan do kit (padrao 9000)")
    parser.add_argument("--org", default=ORG_SLUG_PADRAO, help="organizationSlug do nRF Cloud")
    parser.add_argument("--proj", default=PROJECT_SLUG_PADRAO, help="projectSlug do nRF Cloud")
    parser.add_argument("--tenant-id", default=TENANT_ID_PADRAO,
                         help="tenantId (header x-nrfcloud-tenantid)")
    args = parser.parse_args()

    token = os.environ.get("NRFCLOUD_OAT")
    if not token:
        print("Erro: defina NRFCLOUD_OAT (Organization Auth Token do nRF Cloud) no ambiente.",
              file=sys.stderr)
        sys.exit(1)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", args.porta))
    sock.listen(1)
    print(f"Ouvindo na porta {sock.getsockname()[1]}. Aperte o sw0 no kit para varrer.")

    try:
        while True:
            conexao, endereco = sock.accept()
            print(f"\nConexao de {endereco[0]}:{endereco[1]}")
            try:
                aps = _receber_scan(conexao)
            finally:
                conexao.close()

            if not aps:
                print("Nenhum ponto de acesso valido recebido; nada a resolver.")
                continue

            print(f"{len(aps)} ponto(s) de acesso recebido(s):")
            for ap in aps:
                print(_formatar_ap(ap))

            if len(aps) < 2:
                print("Menos de dois pontos de acesso -- o nRF Cloud exige pelo "
                      "menos dois; pulando a chamada.")
                continue

            try:
                lat, lon, incerteza = resolver(aps, args.org, args.proj, token, args.tenant_id)
            except Exception as exc:  # noqa: BLE001 -- reportar e continuar, nao derrubar o loop
                print(f"Falha ao resolver a posicao: {exc}", file=sys.stderr)
                continue

            print(f"Posicao: lat={lat} lon={lon} incerteza={incerteza} m")
    except KeyboardInterrupt:
        pass
    finally:
        sock.close()


if __name__ == "__main__":
    main()
