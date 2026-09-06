/* Codigo do curso (nrf-manaus-2).
 *
 * Implementacao TCP da interface transporte.h. As variantes HTTP e MQTT
 * (Task 8) entram neste mesmo arquivo, cada uma sob o seu proprio
 * "#if defined(CONFIG_LAB_TRANSPORTE_...)" -- o main.c nao muda.
 *
 * Usa a API nativa de sockets do Zephyr (prefixo zsock_/NET_) em vez dos
 * nomes BSD sem prefixo: nesta versao do SDK os nomes sem prefixo (AF_INET,
 * struct sockaddr_in, socket(), connect()...) só existem via o modo de
 * compatibilidade de namespace (CONFIG_NET_NAMESPACE_COMPAT_MODE, ligado por
 * padrao) ou exigem CONFIG_POSIX_API. Os nomes com prefixo sao os que o
 * proprio Zephyr usa internamente (por exemplo subsys/net/lib/mqtt) e nao
 * dependem de nenhum dos dois.
 */
#if defined(CONFIG_LAB_TRANSPORTE_TCP)

#include <errno.h>

#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/net/socket.h>

#include "transporte.h"

LOG_MODULE_REGISTER(lab_transporte, CONFIG_LOG_DEFAULT_LEVEL);

static int sock = -1;

int transporte_abrir(void)
{
	struct net_sockaddr_in endereco = {0};
	int ret;

	sock = zsock_socket(NET_AF_INET, NET_SOCK_STREAM, 0);
	if (sock < 0) {
		LOG_ERR("Falha ao criar o socket (%d)", -errno);
		return -errno;
	}

	endereco.sin_family = NET_AF_INET;
	endereco.sin_port = net_htons(CONFIG_LAB_PORTA);

	ret = net_addr_pton(NET_AF_INET, CONFIG_LAB_SERVIDOR_IP, &endereco.sin_addr);
	if (ret < 0) {
		LOG_ERR("CONFIG_LAB_SERVIDOR_IP invalido: %s", CONFIG_LAB_SERVIDOR_IP);
		zsock_close(sock);
		sock = -1;
		return ret;
	}

	ret = zsock_connect(sock, (struct net_sockaddr *)&endereco, sizeof(endereco));
	if (ret < 0) {
		LOG_ERR("Falha ao conectar em %s:%d (%d)",
			CONFIG_LAB_SERVIDOR_IP, CONFIG_LAB_PORTA, -errno);
		zsock_close(sock);
		sock = -1;
		return -errno;
	}

	LOG_INF("Conectado em %s:%d", CONFIG_LAB_SERVIDOR_IP, CONFIG_LAB_PORTA);
	return 0;
}

int transporte_enviar(const char *buf, size_t len)
{
	ssize_t ret;

	if (sock < 0) {
		return -ENOTCONN;
	}

	ret = zsock_send(sock, buf, len, 0);
	if (ret < 0) {
		return -errno;
	}
	return (int)ret;
}

int transporte_receber(char *buf, size_t len, k_timeout_t espera)
{
	struct zsock_pollfd pfd = {
		.fd = sock,
		.events = ZSOCK_POLLIN,
	};
	int timeout_ms;
	int ret;

	if (sock < 0) {
		return -ENOTCONN;
	}

	timeout_ms = K_TIMEOUT_EQ(espera, K_FOREVER) ? -1 : (int)k_ticks_to_ms_floor64(espera.ticks);

	ret = zsock_poll(&pfd, 1, timeout_ms);
	if (ret < 0) {
		return -errno;
	}
	if (ret == 0) {
		return 0;
	}

	ret = zsock_recv(sock, buf, len, 0);
	if (ret < 0) {
		return -errno;
	}
	return ret;
}

void transporte_fechar(void)
{
	if (sock >= 0) {
		zsock_close(sock);
		sock = -1;
	}
}

#endif /* CONFIG_LAB_TRANSPORTE_TCP */
