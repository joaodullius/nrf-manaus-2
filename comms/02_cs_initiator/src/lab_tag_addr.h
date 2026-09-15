/*
 * ARQUIVO DO CURSO (nrf-manaus-2) — nao existe no SDK.
 *
 * Endereco BLE do TAG do aluno, digitado no terminal serial no boot.
 * Mesmo mecanismo do edge_ai/03_central_uart; copiado igual nos tres
 * initiators de Channel Sounding (comms/02, comms/03/initiator, comms/05).
 */

#ifndef LAB_TAG_ADDR_H_
#define LAB_TAG_ADDR_H_

#include <zephyr/bluetooth/addr.h>

/* Pede o endereco no console serial e so retorna com um valido. */
void lab_tag_addr_read(bt_addr_le_t *addr);

#endif /* LAB_TAG_ADDR_H_ */
