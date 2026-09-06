/* Codigo do curso (nrf-manaus-2).
 *
 * Uma interface, tres implementacoes (TCP, HTTP, MQTT). O main.c nao sabe qual
 * esta compilada: e a tese do bloco — mesmo payload, transporte trocado.
 */
#ifndef LAB_TRANSPORTE_H_
#define LAB_TRANSPORTE_H_

#include <stddef.h>
#include <zephyr/kernel.h>

/* Todas as funcoes abaixo sao seguras para chamar de threads diferentes ao
 * mesmo tempo: a implementacao serializa o acesso ao descritor internamente
 * (um mutex por transporte), entao quem chama nunca precisa coordenar isso
 * por fora. Uma reabertura (fechar seguido de abrir) nunca deixa o descritor
 * antigo pendurado nem corre com um envio/recebimento em andamento.
 */
int transporte_abrir(void);
int transporte_enviar(const char *buf, size_t len);
/* Devolve bytes lidos (>0); 0 se nada chegou dentro de `espera` (timeout --
 * conexao presumida viva, so tentar de novo); -ECONNRESET se o outro lado
 * fechou a conexao (recv() devolveu 0) -- quem chama deve fechar e reabrir o
 * transporte antes de confiar nele de novo; outro valor negativo em erro de
 * rede, que tambem deve ser tratado como motivo para reabrir.
 */
int transporte_receber(char *buf, size_t len, k_timeout_t espera);
void transporte_fechar(void);

#endif /* LAB_TRANSPORTE_H_ */
