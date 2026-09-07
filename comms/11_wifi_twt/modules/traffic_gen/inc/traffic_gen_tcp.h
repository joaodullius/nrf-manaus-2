/*
 * ORIGEM: copia de arquivo do SDK — nao e codigo do curso.
 *   SDK     : nRF Connect SDK v3.4.0
 *   Upstream: nrf/samples/wifi/twt/modules/traffic_gen/inc/traffic_gen_tcp.h
 *   Local   : C:/ncs/v3.4.0/nrf/samples/wifi/twt/modules/traffic_gen/inc/traffic_gen_tcp.h
 *   Copiado : 2026-09-06 — curso nrf-manaus-2, modulo comms/11_wifi_twt
 *
 * Para conferir se divergiu do SDK:
 *   diff <este arquivo> C:/ncs/v3.4.0/nrf/samples/wifi/twt/modules/traffic_gen/inc/traffic_gen_tcp.h
 *
 * DIVERGENCIA DO CURSO: nenhuma - byte a byte igual ao SDK (conferido em
 * 2026-09-06, ignorando fim de linha).
 *
 * Copyright (c) 2023 Nordic Semiconductor ASA
 *
 * SPDX-License-Identifier: LicenseRef-Nordic-5-Clause
 */

#ifndef __TRAFFIC_GEN_TCP_H__
#define __TRAFFIC_GEN_TCP_H__

extern struct traffic_gen_report remote_report;

/* tcp client/server function prototypes */
int init_tcp_client(struct traffic_gen_config *tg_config);
int send_tcp_uplink_traffic(struct traffic_gen_config *tg_config);
int init_tcp_server(struct traffic_gen_config *tg_config);
int recv_tcp_downlink_traffic(struct traffic_gen_config *tg_config);

#endif /* __TRAFFIC_GEN_TCP_H__ */
