#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Formato CSV do firmware do lab 5 (05_cs_iq_music) — codigo do curso.

O que a serial entrega, por procedure de Channel Sounding (csv_dump_report() em
src/main.c):

    IQ,<counter>,<ap>,<canal 2..76>,<i_local>,<q_local>,<i_remote>,<q_remote>   x75
    CS,<counter>,<ap>,<tone_quality 1/0>,<ifft>,<phase_slope>,<rtt>,<rtt_count>,<rtt_half_ns>

Antes disso, no boot, o firmware pede o endereco do TAG na mesma serial:

    Endereco BLE do tag (ex.: EC:EF:40:2D:5E:46 random):

e so comeca a varrer depois de uma resposta valida. TAG_PROMPT/is_tag_prompt()
e responder_tag() sao o que os scripts usam para reconhecer e responder.

Este modulo so le e escreve esse formato. Quem calcula e cs_de_numpy.py.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

NCH = 75
CH_OFFSET = 2          # CHANNEL_INDEX_OFFSET do firmware: indice 0 = canal 2

TAG_PROMPT = "Endereco BLE do tag"


def is_tag_prompt(line: str) -> bool:
    return TAG_PROMPT in line


def responder_tag(serial_port, tag: str | None) -> None:
    """Manda o endereco do TAG para o firmware, se houver um.

    O firmware so le a serial enquanto esta no prompt; se ja passou dele, a
    linha e ignorada — por isso pode ser mandada sempre que a porta abre.
    """
    if tag:
        serial_port.write((tag.strip() + "\r\n").encode("ascii"))
        serial_port.flush()


def _f(s: str) -> float:
    return float(s)    # aceita "nan", "inf", "-1.500"


def parse_line(line: str):
    parts = line.strip().split(",")
    try:
        if parts[0] == "IQ" and len(parts) == 8:
            return ("IQ", int(parts[1]), int(parts[2]), int(parts[3]),
                    _f(parts[4]), _f(parts[5]), _f(parts[6]), _f(parts[7]))
        if parts[0] == "CS" and len(parts) == 9:
            return ("CS", int(parts[1]), int(parts[2]), int(parts[3]),
                    _f(parts[4]), _f(parts[5]), _f(parts[6]), int(parts[7]), int(parts[8]))
    except ValueError:
        return None
    return None


def format_iq(counter, ap, ch, i_l, q_l, i_r, q_r) -> str:
    return f"IQ,{counter},{ap},{ch},{i_l:.1f},{q_l:.1f},{i_r:.1f},{q_r:.1f}\n"


def format_cs(counter, ap, tq, ifft, phase_slope, rtt, rtt_count, rtt_half_ns) -> str:
    return (f"CS,{counter},{ap},{tq},{ifft:.3f},{phase_slope:.3f},{rtt:.3f},"
            f"{rtt_count},{rtt_half_ns}\n")


@dataclass
class Procedure:
    counter: int
    ap: int
    i_local: np.ndarray = field(default_factory=lambda: np.zeros(NCH))
    q_local: np.ndarray = field(default_factory=lambda: np.zeros(NCH))
    i_remote: np.ndarray = field(default_factory=lambda: np.zeros(NCH))
    q_remote: np.ndarray = field(default_factory=lambda: np.zeros(NCH))
    seen: set = field(default_factory=set)
    tone_quality_ok: bool = False
    fw: dict = field(default_factory=dict)
    rtt_count: int = 0
    rtt_half_ns: int = 0
    complete: bool = False

    def comb(self) -> np.ndarray:
        return (self.i_local + 1j * self.q_local) * (self.i_remote + 1j * self.q_remote)


def read_procedures(path) -> list[Procedure]:
    """Le o arquivo capturado e devolve so as procedures completas, em ordem."""
    pending: dict[tuple[int, int], Procedure] = {}
    done: list[Procedure] = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for raw in f:
            rec = parse_line(raw)
            if rec is None:
                continue
            key = (rec[1], rec[2])
            proc = pending.setdefault(key, Procedure(counter=rec[1], ap=rec[2]))
            if rec[0] == "IQ":
                idx = rec[3] - CH_OFFSET
                if 0 <= idx < NCH:
                    proc.i_local[idx], proc.q_local[idx] = rec[4], rec[5]
                    proc.i_remote[idx], proc.q_remote[idx] = rec[6], rec[7]
                    proc.seen.add(idx)
            else:
                proc.tone_quality_ok = rec[3] == 1
                proc.fw = {"ifft": rec[4], "phase_slope": rec[5], "rtt": rec[6]}
                proc.rtt_count, proc.rtt_half_ns = rec[7], rec[8]
                if len(proc.seen) == NCH:
                    proc.complete = True
                    done.append(proc)
                del pending[key]
    return done


def group_by_counter(procs) -> dict[int, list[Procedure]]:
    """{ranging counter: [Procedure por caminho de antena, ap crescente]}.

    Com CONFIG_LAB_ANTENNA_PATHS=2 o firmware despeja a mesma procedure duas
    vezes (ap 0 e ap 1). read_procedures() as devolve separadas; aqui elas se
    reencontram pelo counter, para comparar um caminho contra os dois sobre a
    MESMA medida.
    """
    out: dict[int, list[Procedure]] = {}
    for p in procs:
        out.setdefault(p.counter, []).append(p)
    for v in out.values():
        v.sort(key=lambda p: p.ap)
    return out
