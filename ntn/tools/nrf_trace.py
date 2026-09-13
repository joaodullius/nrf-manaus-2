"""Converte dumps binarios de trace do modem nRF91 chamando `nrfutil trace lte`.

Duas armadilhas de tempo que este modulo evita:

1. A interface grafica nRFInsight aplica o campo Timebase com escala errada,
   somando o valor em segundos a um campo contado em microssegundos. Os
   timestamps do TXT exportado por ela nao sao hora de relogio.

2. O proprio `nrfutil trace lte` soma o timestamp do modem, que e um contador
   de uptime, a epoca do cabecalho do .bin, que ja e absoluta. Isso conta o
   uptime duas vezes e joga o log horas para a frente.

A referencia correta e o campo `initial_trace_timestamp_epoch_us` do cabecalho,
que marca o primeiro registro. Deste modulo saem timestamps ancorados nele,
usando apenas os intervalos relativos que o nrfutil imprime.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

_EPOCH_RE = re.compile(rb"initial_trace_timestamp_epoch_us:\s*(\d+)")
_HEADER_BYTES = 256
_LINE_RE = re.compile(r"^(\d{2}):(\d{2}):(\d{2})\.(\d{6})[ \t]*(.*)$")
_UNIX_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
_GNSS_RE = re.compile(r"GNSS_POS_REP_PV")
_CCLK_RE = re.compile(r'\+CCLK[:=]?\s*"(\d{2}/\d{2}/\d{2},\d{2}:\d{2}:\d{2})')
_CCLK_WINDOW = timedelta(seconds=60)


# A captura no PC fecha o arquivo alguns segundos depois do ultimo registro do
# modem. Medido em 6 traces com ancora independente (CCLK ou log do terminal):
# 16,2 / 18,3 / 25,7 / 26,4 / 26,5 / 27,0 s. Nao ha explicacao fechada para a
# variacao -- nao acompanha o tamanho do buffer nem a taxa de dados na cauda --
# entao vale o centro da faixa, com a incerteza declarada, e nao um valor exato.
CAPTURE_TAIL_LAG = timedelta(seconds=22)
MTIME_ACCURACY = "+-10 s"
# Janela de sanidade: um mtime muito depois do inicio da captura nao e mais o
# fim dela (arquivo copiado ou tocado localmente perde o carimbo original).
MTIME_SLACK = timedelta(minutes=15)
UNTRUSTWORTHY = "NAO CONFIAVEL"


class TraceError(RuntimeError):
    """Falha ao ler ou converter um trace."""


@dataclass(frozen=True)
class Anchor:
    """De onde saiu a hora absoluta do trace, e o quanto ela vale."""

    kind: str          # "cclk" | "mtime" | "header"
    accuracy: str
    trustworthy: bool


@dataclass(frozen=True)
class TraceRecord:
    """Uma mensagem decodificada do trace."""

    timestamp: datetime  # sempre com fuso, em UTC
    label: str
    text: str


@dataclass(frozen=True)
class TraceLog:
    """Os registros mais a procedencia do relogio. Itera como lista de registros."""

    records: list
    anchor: Anchor

    def __iter__(self):
        return iter(self.records)

    def __len__(self):
        return len(self.records)

    def __getitem__(self, index):
        return self.records[index]


def read_epoch_us(bin_path) -> int:
    """Le a epoca absoluta, em microssegundos, gravada no cabecalho do .bin."""
    with open(bin_path, "rb") as fh:
        head = fh.read(_HEADER_BYTES)
    m = _EPOCH_RE.search(head)
    if not m:
        raise TraceError(
            f"cabecalho 'initial_trace_timestamp_epoch_us' nao encontrado em {bin_path}; "
            "o arquivo nao parece ser um dump de trace do modem"
        )
    return int(m.group(1))


_GPS_EPOCH = datetime(1980, 1, 6, tzinfo=timezone.utc)
_GPS_LEAP_SECONDS = 18          # UTC = GPS - 18 s desde 2017
_MLOG_LABEL = "GNSS_GPS_MLOG_T"
_TOW_FIELD = 7                  # indice do time-of-week, em segundos
GNSS_MIN_SAMPLES = 20
GNSS_ACCURACY = "+-0.5 s"
# Se o deslocamento pedido passar disso, a semana do GPS foi resolvida errada
# ou o campo nao e TOW: melhor recusar que ancorar num dia trocado.
_GNSS_MAX_SHIFT = timedelta(hours=12)


def _tow_to_utc(tow, aproximado):
    """TOW do GPS (segundos na semana) -> UTC, com a semana vinda da estimativa."""
    semana = (aproximado - _GPS_EPOCH).days // 7
    melhor = None
    for w in (semana - 1, semana, semana + 1):
        t = _GPS_EPOCH + timedelta(seconds=w * 604800 + tow - _GPS_LEAP_SECONDS)
        if melhor is None or abs(t - aproximado) < abs(melhor - aproximado):
            melhor = t
    return melhor


def _gnss_shift(parsed):
    """Deslocamento pelo TOW que o receptor GNSS grava, ou None.

    Cada canal loga o TOW do ultimo subframe decodificado, e um subframe GPS
    dura 6 s, entao os valores ficam espalhados por essa janela para tras. O
    maximo e o canal menos atrasado, e e ele que vale como referencia. Exige um
    minimo de amostras: com poucas, o maximo ainda nao alcancou o instante real.
    """
    diffs = []
    for stamp, label, body in parsed:
        if label != _MLOG_LABEL:
            continue
        campos = body[0].split()
        if len(campos) <= _TOW_FIELD:
            continue
        try:
            tow = int(campos[_TOW_FIELD])
        except ValueError:
            continue
        if not 0 < tow < 604800:
            continue
        diffs.append(_tow_to_utc(tow, stamp) - stamp)
    if len(diffs) < GNSS_MIN_SAMPLES:
        return None
    shift = max(diffs)
    return shift if abs(shift) <= _GNSS_MAX_SHIFT else None


def _mtime_anchor(parsed, epoch, mtime_utc):
    """Ancora pelo fim da captura, quando nao ha CCLK. Devolve (shift, Anchor).

    O mtime do .bin, preservado do host que capturou, marca o fechamento do
    arquivo -- alguns segundos depois do ultimo registro. E grosseiro, mas erra
    por segundos em vez dos minutos que a epoca do cabecalho erra.
    """
    if mtime_utc is not None:
        span = parsed[-1][0] - parsed[0][0]
        elapsed = mtime_utc - epoch
        if timedelta(0) < elapsed <= span + MTIME_SLACK:
            shift = (mtime_utc + CAPTURE_TAIL_LAG) - parsed[-1][0]
            return shift, Anchor("mtime", MTIME_ACCURACY, True)
    return timedelta(0), Anchor(
        "header", "inicio da captura, nao o 1o registro", False)


def parse_text(text: str, epoch_us: int, mtime_utc=None) -> TraceLog:
    """Converte a saida textual do nrfutil em registros com timestamp absoluto.

    Os horarios impressos pelo nrfutil sao usados apenas como intervalos: o
    primeiro registro e ancorado em `epoch_us` e os demais seguem os deltas.
    Assim o fuso da maquina nao influencia o resultado, e a soma indevida do
    uptime feita pelo nrfutil desaparece.
    """
    epoch = _UNIX_EPOCH + timedelta(microseconds=epoch_us)

    parsed: list[tuple[datetime, str, list[str]]] = []
    first_tod = None
    prev_tod = None
    day = 0

    for raw in text.splitlines():
        m = _LINE_RE.match(raw)
        if not m:
            if not parsed:
                raise TraceError(f"primeira linha do nrfutil sem timestamp: {raw!r}")
            parsed[-1][2].append(raw.rstrip())
            continue

        hh, mm, ss, us, rest = m.groups()
        tod = timedelta(hours=int(hh), minutes=int(mm),
                        seconds=int(ss), microseconds=int(us))

        if first_tod is None:
            first_tod = tod
        elif tod < prev_tod:
            day += 1          # o log atravessou a meia-noite
        prev_tod = tod

        label, _, body = rest.partition(" ")
        stamp = epoch + (tod + timedelta(days=day) - first_tod)
        parsed.append((stamp, label, [body.rstrip()]))

    # O +CCLK derivado do GNSS, quando existe, e melhor referencia que a epoca
    # do cabecalho, que nos traces medidos adianta cerca de seis minutos.
    shift = _gnss_shift(parsed)
    if shift is not None:
        anchor = Anchor("gnss", GNSS_ACCURACY, True)
    else:
        shift = _cclk_shift(parsed)
        if shift is not None:
            anchor = Anchor("cclk", "sub-segundo", True)
        else:
            shift, anchor = _mtime_anchor(parsed, epoch, mtime_utc)
    records = [
        TraceRecord(timestamp=stamp + shift, label=label, text="\n".join(body))
        for stamp, label, body in parsed
    ]
    return TraceLog(records=records, anchor=anchor)


def _cclk_shift(parsed):
    """Deslocamento para ancorar no +CCLK que segue um fix de GNSS, ou None.

    O modem emite AT+CCLK com a hora derivada do GNSS logo apos o fix. Essa e a
    melhor referencia de relogio disponivel no trace. Um +CCLK solto e ignorado,
    porque pode ser resquicio de uma sessao anterior.
    """
    pending = None
    for stamp, label, body in parsed:
        text = label + " " + " ".join(body)
        if pending is not None and stamp - pending > _CCLK_WINDOW:
            pending = None
        if pending is not None:
            m = _CCLK_RE.search(text)
            if m:
                real = datetime.strptime(m.group(1), "%y/%m/%d,%H:%M:%S")
                return real.replace(tzinfo=timezone.utc) - stamp
        if _GNSS_RE.search(text):
            pending = stamp
    return None


def convert(bin_path, db_path, nrfutil: str = "nrfutil", mtime_utc=None) -> TraceLog:
    """Decodifica um .bin usando o trace database .tar.gz e devolve os registros.

    Requer o componente `trace` do nRF Util, que se instala com `nrfutil install trace`.
    """
    exe = shutil.which(nrfutil)
    if exe is None:
        raise TraceError(
            f"executavel {nrfutil!r} nao encontrado no PATH; instale o nRF Util "
            "e depois o componente com 'nrfutil install trace'"
        )
    epoch_us = read_epoch_us(bin_path)
    proc = subprocess.run(
        [exe, "trace", "lte",
         "--input-file", str(bin_path),
         "--database-config", str(db_path),
         "--x-output-modem-txt-stdout"],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip()
        if "command `trace` not found" in detail:
            detail += "\nrode 'nrfutil install trace' para instalar o componente"
        raise TraceError(f"nrfutil saiu com codigo {proc.returncode}: {detail}")
    if mtime_utc is None:
        mtime_utc = datetime.fromtimestamp(os.path.getmtime(bin_path), timezone.utc)
    return parse_text(proc.stdout, epoch_us, mtime_utc)


def write_txt(log, out_path) -> None:
    """Grava o log como texto, um registro por linha, com data e hora em UTC.

    Aceita um TraceLog ou uma lista crua de registros. Com o TraceLog, a
    primeira linha declara de onde veio a hora absoluta: sem essa marca um
    trace mal ancorado passa por bom e contamina a correlacao com a passagem.
    """
    records = getattr(log, "records", log)
    anchor = getattr(log, "anchor", None)
    with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
        if anchor is not None:
            aviso = "" if anchor.trustworthy else f"  {UNTRUSTWORTHY}"
            fh.write(f"# anchor: {anchor.kind} ({anchor.accuracy}){aviso}\n")
        for r in records:
            stamp = r.timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")
            fh.write(f"{stamp} {r.label} {r.text}\n".replace(" \n", "\n"))
