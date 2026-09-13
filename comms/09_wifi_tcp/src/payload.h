/*
 * Codigo do curso (nrf-manaus-2) — nao vem do SDK.
 *
 * Monta a linha JSON que os labs 9, 10 e 13 mandam pelo transporte escolhido.
 * O formato esta espelhado em tools/payload_ref.py, que os testes cobrem.
 */
#ifndef LAB_PAYLOAD_H_
#define LAB_PAYLOAD_H_

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

struct payload_amostra {
	uint32_t seq;
	uint32_t uptime_ms;
	int16_t temp_cc;     /* centesimos de grau: 2537 = 25,37 C */
	int8_t rssi_dbm;
	bool botao;
};

/* Escreve a linha JSON (terminada em \n) em buf. Devolve os bytes escritos,
 * ou -ENOMEM se nao couber.
 */
int payload_montar(char *buf, size_t buf_len, const struct payload_amostra *a);

#endif /* LAB_PAYLOAD_H_ */
