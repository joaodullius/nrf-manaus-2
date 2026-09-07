# Scripts de captura da Parte A

Os cinco scripts que produziram **cada tabela** da Parte A do README deste lab.
Todos rodam contra o firmware do **lab 6** (o shell) — nenhum usa o firmware
deste diretório, que só serve para a Parte B (TWT).

| Script | O que produziu no README |
|---|---|
| `escada_corrente.py` | a escada por corrente e a anatomia do despertar |
| `escada_latencia.py` | a escada por latência (a segunda corrida) |
| `teto_listen_interval.py` | até onde o listen interval é aceito, associa e responde |
| `li_longo.py` | os regimes de 10 s, 30 s e 72 s de sono, e o patamar de 31 µA |
| `ping_continuo.py` | 1 resposta em 481 pings com listen interval 600 |

`bancada.py` reúne o que os cinco repetiam: abrir o PPK2 na ordem certa, falar
com o shell e segmentar os pulsos de despertar.

## Antes de rodar

```
pip install pyserial ppk2-api
```

O PPK2 precisa estar em **amperímetro** no **P10** da EB II, com o **SB10
cortado** — o ponto de medição e a decisão de bancada estão no README do lab.
Anote a porta do console (a **primeira** VCOM, porque o shield troca a UART), a
porta do PPK2 e o serial do J-Link (`nrfutil device list`).

```
python escada_corrente.py --shell COM21 --ppk2 COM3 --jlink 1051898754 ^
    --ssid "MinhaRede" --senha "..." --saida escada_psm.json
```

Todos aceitam os mesmos seis argumentos; `--help` mostra os extras de cada um.

> **A senha vai na linha de comando**, e por isso ela fica no histórico do
> terminal. Nenhum destes scripts guarda credencial, e nenhum arquivo `.json` de
> saída contém a senha — mas limpe o histórico se a máquina for compartilhada.

## As duas regras que custaram reinícios

1. **Feche a chave do PPK2 antes de resetar a DK.** Todos os scripts fazem isso
   nesta ordem. Ao contrário, o driver inicia com o companion sem VBAT e tudo
   falha com `RPU is unresponsive for 10 sec`.
2. **Enquanto o script vive, a chave fica fechada; quando ele termina, o PPK2 a
   abre** e o companion cai. Por isso até o `escada_latencia.py`, que não mede
   corrente nenhuma, abre o PPK2 e o mantém vivo. Entre um script e outro, ou
   recoloque o jumper no P10, ou conte com o reset que o próximo faz.
