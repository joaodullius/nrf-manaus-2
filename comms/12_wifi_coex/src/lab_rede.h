/*
 * ARQUIVO DO CURSO (nrf-manaus-2) — nao existe no SDK.
 *
 * Rede Wi-Fi do aluno (SSID e senha) e, nos labs que mandam dados para o PC,
 * IP e porta do servidor: digitados no terminal serial e gravados em settings.
 * Mesmo mecanismo do lab_tag_addr dos initiators de Channel Sounding; copiado
 * igual nos labs de Wi-Fi que precisam da rede da sala (07, 09, 11, 12, 13).
 */

#ifndef LAB_REDE_H_
#define LAB_REDE_H_

#include <stdbool.h>
#include <stdint.h>

/*
 * Le a rede gravada em settings. Se nao houver, pergunta no console e grava.
 * Se houver, mostra o que tem e espera uma tecla por alguns segundos: Enter
 * ou nenhuma tecla usa o gravado; qualquer outra tecla pede tudo de novo.
 *
 * Deixa a credencial na biblioteca wifi_credentials, entao a conexao segue
 * por NET_REQUEST_WIFI_CONNECT_STORED, como no sample da Nordic.
 *
 * pede_servidor: tambem pergunta IP e porta do servidor no PC.
 * porta_padrao : o que Enter vazio escolhe no prompt da porta.
 *
 * So retorna com tudo valido.
 */
void lab_rede_ler(bool pede_servidor, uint16_t porta_padrao);

/* Validos depois de lab_rede_ler(). */
const char *lab_rede_ssid(void);
const char *lab_rede_ip(void);
uint16_t lab_rede_porta(void);

#endif /* LAB_REDE_H_ */
