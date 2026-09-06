/*
 * Harness de teste para payload.c -- existe SO para o teste de travessia
 * C-Python (tools/tests/test_payload_c.py). Nao faz parte do lab: o
 * firmware real chama payload_montar() a partir do app Zephyr, nao deste
 * arranjo de linha de comando.
 *
 * Uso:
 *   harness_payload <seq> <uptime_ms> <temp_cc> <rssi_dbm> <botao:0|1> [buf_len]
 *
 * Compila junto com src/payload.c num binario de host, sem depender de
 * nada do Zephyr -- payload.c e payload.h so usam a biblioteca padrao C
 * (stdio.h, errno.h, stdbool.h, stddef.h, stdint.h).
 *
 * Em caso de sucesso, escreve em stdout exatamente os bytes que
 * payload_montar() escreveu no buffer, sem nenhuma transformacao (por
 * isso o modo binario de stdout no Windows, ver abaixo). Em caso de erro
 * (retorno negativo de payload_montar, por exemplo -ENOMEM por buffer
 * pequeno demais), escreve "ERRO:<n>\n" em vez disso.
 */
#include <stdio.h>
#include <stdlib.h>

#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#endif

#include "payload.h"

int main(int argc, char **argv)
{
	struct payload_amostra a;
	char *buf;
	size_t buf_len;
	int n;

	if (argc < 6) {
		fprintf(stderr,
			"uso: %s seq uptime_ms temp_cc rssi_dbm botao[0|1] [buf_len]\n",
			argv[0]);
		return 2;
	}

#ifdef _WIN32
	/* Sem isso, o runtime do Windows troca cada \n por \r\n na saida e a
	 * comparacao byte a byte com payload_ref.py (que so usa \n) falha.
	 */
	_setmode(_fileno(stdout), _O_BINARY);
#endif

	a.seq = (uint32_t)strtoul(argv[1], NULL, 10);
	a.uptime_ms = (uint32_t)strtoul(argv[2], NULL, 10);
	a.temp_cc = (int16_t)atoi(argv[3]);
	a.rssi_dbm = (int8_t)atoi(argv[4]);
	a.botao = atoi(argv[5]) != 0;

	buf_len = (argc >= 7) ? (size_t)strtoul(argv[6], NULL, 10) : 256;
	if (buf_len == 0) {
		buf_len = 1;
	}
	buf = malloc(buf_len);
	if (!buf) {
		fprintf(stderr, "sem memoria para buf_len=%zu\n", buf_len);
		return 3;
	}

	n = payload_montar(buf, buf_len, &a);

	if (n < 0) {
		printf("ERRO:%d\n", n);
	} else {
		fwrite(buf, 1, (size_t)n, stdout);
	}

	free(buf);
	return 0;
}
