/* Codigo do curso (nrf-manaus-2).
 *
 * Uma interface, tres implementacoes (TCP, HTTP, MQTT). O main.c nao sabe qual
 * esta compilada: e a tese do bloco — mesmo payload, transporte trocado.
 */
#ifndef LAB_TRANSPORTE_H_
#define LAB_TRANSPORTE_H_

#include <stddef.h>
#include <zephyr/kernel.h>

int transporte_abrir(void);
int transporte_enviar(const char *buf, size_t len);
/* Devolve bytes lidos, 0 se nada chegou dentro de `espera`, ou negativo em erro. */
int transporte_receber(char *buf, size_t len, k_timeout_t espera);
void transporte_fechar(void);

#endif /* LAB_TRANSPORTE_H_ */
