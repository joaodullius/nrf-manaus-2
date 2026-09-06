/* Codigo do curso (nrf-manaus-2). Espelhado em tools/payload_ref.py. */
#include <errno.h>
#include <stdio.h>

#include "payload.h"

/* Limitacao conhecida: para temp_cc entre -99 e -1 (ou seja, entre -0,99 e
 * -0,01 C), a divisao inteira a->temp_cc / 100 arredonda para 0 e o sinal se
 * perde, imprimindo "0.XX" em vez de "-0.XX". A bancada do curso nao chega
 * perto de 0 C, e o payload_ref.py (usado pelo servidor para interpretar)
 * nao tem esse problema, pois divide em ponto flutuante.
 */
int payload_montar(char *buf, size_t buf_len, const struct payload_amostra *a)
{
	int n = snprintf(buf, buf_len,
			 "{\"seq\":%u,\"uptime_ms\":%u,\"temp_c\":%d.%02d,"
			 "\"rssi_dbm\":%d,\"botao\":%s}\n",
			 a->seq, a->uptime_ms,
			 a->temp_cc / 100, (a->temp_cc < 0 ? -a->temp_cc : a->temp_cc) % 100,
			 a->rssi_dbm, a->botao ? "true" : "false");

	if (n < 0 || (size_t)n >= buf_len) {
		return -ENOMEM;
	}
	return n;
}
