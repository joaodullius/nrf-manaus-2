#!/usr/bin/env python3
"""
fwd_to_lab.py — junta as gravacoes do Data Forwarder Host no CSV que o Edge AI
Lab aceita.

Codigo do curso nrf-manaus-2 (nao vem do SDK). So stdlib.

O Host grava um CSV por classe:

    device_time_ms,ax,ay,az,gx,gy,gz,temp,hum,pres,label
    33203,119713.0,-241821.0,10011659.0,-2663.0,-4261.0,-1597.0,24030000.0,...,idle

O Lab quer um arquivo unico, um alvo inteiro a partir de 0 e valores numericos.
Os valores ficam EXATAMENTE como o Host gravou — micro-unidades SI do Zephyr,
em float — e o Lab os detecta como FLOAT32. Nao ha conversao de escala: a app
de inferencia alimenta o modelo na mesma escala (sensor_value_to_micro()).

O que este script faz:
  - descarta device_time_ms (o Lab nao precisa dele)
  - troca o label texto por inteiro, na ordem dada em --classes
  - concatena na ordem dos arquivos, sem embaralhar
  - valida as regras do Lab antes de gravar (>= 2 classes, >= 20 amostras por
    classe, classe 0 presente, nada vazio) e sai com codigo 1 se falhar

Opcoes:
  --drop-env      tira temp/hum/pres aqui em vez de no Lab ("Remove variables")
  --session-col   acrescenta 'session' = indice do arquivo (Session ID no Lab)

Uso:
    python tools/fwd_to_lab.py info  recordings/*.csv
    python tools/fwd_to_lab.py merge recordings/*.csv --classes idle,vel1,vel2,vel3 --out dataset.csv
"""

import argparse
import csv
import glob
import statistics
import sys
from pathlib import Path

TIME_COL = "device_time_ms"
LABEL_COL = "label"
IMU_COLS = ["ax", "ay", "az", "gx", "gy", "gz"]
ENV_COLS = ["temp", "hum", "pres"]
MICRO = 1_000_000.0
LAB_MIN_PER_CLASS = 20


def expand(paths):
    out = []
    for p in paths:
        hits = sorted(glob.glob(p))
        out.extend(hits if hits else [p])
    return out


def read_recording(path):
    """Le um CSV do Host. Devolve (header, rows) ja validados no basico."""
    with open(path, newline="", encoding="utf-8") as f:
        rd = csv.reader(f)
        header = next(rd, None)
        if not header:
            sys.exit(f"{path}: arquivo vazio")
        if header[0] != TIME_COL or header[-1] != LABEL_COL:
            sys.exit(f"{path}: header nao e do Data Forwarder Host "
                     f"(esperado '{TIME_COL},...,{LABEL_COL}', veio {header})")
        rows = []
        for n, r in enumerate(rd, start=2):
            if len(r) != len(header):
                sys.exit(f"{path}:{n}: {len(r)} colunas, header tem {len(header)}")
            if any(c.strip() == "" for c in r):
                sys.exit(f"{path}:{n}: valor vazio — o Lab recusa")
            rows.append(r)
    if not rows:
        sys.exit(f"{path}: sem linhas de dados")
    missing = [c for c in IMU_COLS if c not in header]
    if missing:
        sys.exit(f"{path}: faltam canais do IMU no header: {missing}")
    return header, rows


def stats(header, rows):
    it = header.index(TIME_COL)
    t = [int(float(r[it])) for r in rows]
    span = (t[-1] - t[0]) / 1000.0 if len(t) > 1 else 0.0
    rate = (len(t) - 1) / span if span > 0 else 0.0
    gaps = [b - a for a, b in zip(t, t[1:])]
    lost = sum((g // 10 - 1) for g in gaps if g > 10)
    back = sum(1 for g in gaps if g < 0)
    labels = sorted({r[header.index(LABEL_COL)] for r in rows})
    iaz, igx = header.index("az"), header.index("gx")
    az_sd = statistics.pstdev(float(r[iaz]) for r in rows) / MICRO
    gx_sd = statistics.pstdev(float(r[igx]) for r in rows) / MICRO
    return dict(rows=len(rows), span=span, rate=rate, lost=lost, back=back,
                labels=labels, az_sd=az_sd, gx_sd=gx_sd)


def cmd_info(args):
    for path in expand(args.files):
        header, rows = read_recording(path)
        s = stats(header, rows)
        print(f"{Path(path).name}")
        print(f"  linhas {s['rows']}  duracao {s['span']:.1f} s  taxa {s['rate']:.2f} Hz"
              f"  perdidas {s['lost']}  labels {s['labels']}")
        print(f"  desvio-padrao: az {s['az_sd']:.3f} m/s2  gx {s['gx_sd']:.3f} rad/s")
        if s["back"]:
            print(f"  AVISO: device_time_ms anda para tras {s['back']}x — duas sessoes no mesmo arquivo?")


def cmd_merge(args):
    files = expand(args.files)
    if not files:
        sys.exit("nenhum arquivo")

    classes = [c.strip() for c in args.classes.split(",")] if args.classes else None

    loaded = []
    seen = []
    for path in files:
        header, rows = read_recording(path)
        il = header.index(LABEL_COL)
        labels = {r[il] for r in rows}
        if len(labels) != 1:
            sys.exit(f"{path}: mais de um label no mesmo arquivo {sorted(labels)}")
        label = labels.pop()
        if label not in seen:
            seen.append(label)
        loaded.append((path, header, rows, label))

    ref = [c for c in loaded[0][1] if c not in (TIME_COL, LABEL_COL)]
    for path, header, _, _ in loaded[1:]:
        cols = [c for c in header if c not in (TIME_COL, LABEL_COL)]
        if cols != ref:
            sys.exit(f"{path}: canais {cols} diferem do primeiro arquivo {ref}")

    if classes is None:
        classes = sorted(seen)
        print(f"AVISO: --classes nao dado; usando ordem alfabetica {classes}. "
              f"Anote o dicionario — a app precisa dele.", file=sys.stderr)
    unknown = [l for l in seen if l not in classes]
    if unknown:
        sys.exit(f"labels sem classe em --classes: {unknown} (classes: {classes})")
    absent = [c for c in classes if c not in seen]
    if absent:
        sys.exit(f"classes em --classes sem arquivo: {absent}")
    class_id = {c: i for i, c in enumerate(classes)}
    if len(classes) < 2:
        sys.exit("DATASET INVALIDO para o Lab: menos de 2 classes (nada gravado)")

    keep = [c for c in ref if not (args.drop_env and c in ENV_COLS)]
    out_cols = list(keep)
    if args.session_col:
        out_cols.append("session")
    out_cols.append("class")

    count = {c: 0 for c in classes}
    written = 0
    with open(args.out, "w", newline="\n", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(out_cols)
        for session, (path, header, rows, label) in enumerate(loaded):
            idx = [header.index(c) for c in keep]
            cid = class_id[label]
            for r in rows:
                vals = [r[i] for i in idx]          # verbatim: o Host ja escreve float
                if args.session_col:
                    vals.append(session)
                vals.append(cid)
                w.writerow(vals)
            count[label] += len(rows)
            written += len(rows)
            s = stats(header, rows)
            print(f"{Path(path).name}: {len(rows)} linhas -> class {cid} ({label}), "
                  f"{s['rate']:.2f} Hz, perdidas {s['lost']}")

    problems = []
    if 0 not in class_id.values():
        problems.append("classe 0 ausente")
    for c, n in count.items():
        if n < LAB_MIN_PER_CLASS:
            problems.append(f"classe {class_id[c]} ({c}) com {n} < {LAB_MIN_PER_CLASS} amostras")
    if problems:
        Path(args.out).unlink(missing_ok=True)
        print("DATASET INVALIDO para o Lab: " + "; ".join(problems), file=sys.stderr)
        sys.exit(1)

    print(f"\n{args.out}: {written} linhas, colunas {out_cols}")
    print("dicionario de classes (a app precisa dele):")
    for c in classes:
        print(f"  {class_id[c]}  {c:<14} {count[c]:>7} amostras")
    env_kept = [c for c in keep if c in ENV_COLS]
    if env_kept:
        print(f"{','.join(env_kept)} mantidas: no Lab, marque-as em 'Remove variables' "
              f"(ou use --drop-env).")
    print("valores em micro-unidades SI, como o Host gravou -> o Lab detecta FLOAT32.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("info", help="taxa, perdas e espalhamento de cada gravacao")
    p.add_argument("files", nargs="+")
    p.set_defaults(fn=cmd_info)

    p = sub.add_parser("merge", help="junta as gravacoes no CSV do Lab")
    p.add_argument("files", nargs="+")
    p.add_argument("--classes", help="labels na ordem das classes 0..N-1, ex.: idle,vel1,vel2,vel3")
    p.add_argument("--out", required=True)
    p.add_argument("--drop-env", action="store_true", help="tira temp/hum/pres aqui em vez de no Lab")
    p.add_argument("--session-col", action="store_true",
                   help="acrescenta coluna 'session' = indice do arquivo (Session ID no Lab)")
    p.set_defaults(fn=cmd_merge)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
