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
/* Contrato de erro comum a transporte_enviar() e transporte_receber(),
 * valido nos tres transportes:
 *
 *   > 0            operacao completa (bytes enviados ou recebidos).
 *   0              (so em transporte_receber) nada chegou dentro de
 *                  `espera` -- timeout, nao erro; conexao presumida viva,
 *                  so tentar de novo.
 *   -ECONNRESET    o outro lado fechou a conexao (TCP: recv() devolveu 0;
 *                  MQTT: MQTT_EVT_DISCONNECT) -- quem chama deve fechar e
 *                  reabrir o transporte antes de confiar nele de novo.
 *   -EBADMSG       erro de APLICACAO, nao de conexao: o transporte
 *                  continua de pe, mas a mensagem foi rejeitada por quem
 *                  esta do outro lado (por exemplo, HTTP respondendo um
 *                  status diferente do esperado a um POST/GET). So o TCP
 *                  puro nunca devolve isso -- ele nao tem uma nocao de
 *                  "aplicacao" separada da conexao. Reabrir o transporte
 *                  NAO resolve esse caso; quem chama so deve registrar e
 *                  seguir (a proxima chamada periodica tenta de novo).
 *   outro negativo  erro de rede -- motivo para reabrir, igual ao
 *                  -ECONNRESET.
 */
int transporte_abrir(void);
int transporte_enviar(const char *buf, size_t len);
int transporte_receber(char *buf, size_t len, k_timeout_t espera);
void transporte_fechar(void);

#endif /* LAB_TRANSPORTE_H_ */
