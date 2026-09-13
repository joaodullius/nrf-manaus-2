# Ferramentas de PC do lab 9 (wifi_tcp)

## `payload_ref.py`

Implementação de referência, em Python, do formato de payload que o firmware
monta em `../src/payload.c`. Uma linha JSON por amostra:

```
{"seq":7,"uptime_ms":1234,"temp_c":25.37,"rssi_dbm":-52,"botao":false}
```

- `montar(seq, uptime_ms, temp_cc, rssi_dbm, botao) -> str`: monta a linha
  (com `\n` no final). `temp_cc` é a temperatura em centésimos de grau,
  igual ao que o firmware manda.
- `parse(linha) -> dict | None`: interpreta uma linha; devolve `None` se não
  for JSON, se faltar algum campo, ou se algum campo tiver o tipo errado
  (por exemplo `"seq"` como string, ou `"botao"` como `0`/`1` em vez de
  `true`/`false`).

É o módulo que o servidor da Task 7 (`wifi_server.py`) importa para
interpretar o que chega do dispositivo.

## Testes (`tests/`)

```bash
cd tools
python -m pytest -q
```

- `tests/vetores_payload.json`: os casos de referência (entrada e saída
  esperada), usados tanto pelos testes só em Python quanto pelo teste de
  travessia C-Python, para o contrato ficar num lugar só.
- `tests/test_payload.py`: testa `payload_ref.py` contra ele mesmo (monta,
  reparsa, rejeita linha inválida, rejeita tipo errado).
- `tests/test_payload_c.py` + `tests/harness_payload.c`: compila
  `../src/payload.c` num binário de host e compara a saída, byte a byte,
  com `payload_ref.montar()`. É essa comparação que prova que o firmware e
  o servidor concordam no formato — os testes só em Python não provam isso
  sozinhos, porque comparam a implementação Python com ela mesma.
  `harness_payload.c` existe só para esse teste: lê os parâmetros da linha
  de comando, chama `payload_montar()` e imprime a linha crua em stdout (ou
  `ERRO:<n>` se o retorno for negativo). Não faz parte do lab.

### Compilador usado pela travessia C-Python

O teste procura um compilador de host nesta ordem: `cc`, `gcc`, `clang`, e
por último `cl.exe` (MSVC), localizado via `vswhere` ou no caminho padrão
de uma instalação "Community" do Visual Studio 2022. `payload.c` e
`payload.h` só usam a biblioteca padrão C (`stdio.h`, `errno.h`,
`stdbool.h`, `stddef.h`, `stdint.h`) — nenhuma dependência do Zephyr foi
emulada nem precisou ser isolada para compilar no host.

Antes de compilar o harness de verdade, o teste compila um "hello world"
mínimo com `<stdio.h>` para confirmar que o compilador achado funciona.
Isso importa porque **ter o `cl.exe` no disco não é suficiente**: numa
instalação do Visual Studio só com o componente "Ferramentas de Build do
C++" (VC++ Build Tools) e sem o componente "SDK do Windows 10/11", o
`cl.exe` existe mas não acha nem `stdio.h` (o UCRT vem do SDK, não do
toolset do VC++). Nesse caso os testes de travessia são **pulados** com
mensagem explicando o que instalar, em vez de falhar como se fosse um bug
em `payload.c`.

Se nenhum compilador utilizável for encontrado, rode `python -m pytest -rs`
para ver o motivo exato nas mensagens de skip.
