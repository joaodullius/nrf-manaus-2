/* Codigo do curso (nrf-manaus-2).
 *
 * Implementacao TCP da interface transporte.h. As variantes HTTP e MQTT
 * (Task 8) entram neste mesmo arquivo, cada uma sob o seu proprio
 * "#if defined(CONFIG_LAB_TRANSPORTE_...)" -- o main.c nao muda.
 *
 * Usa a API nativa de sockets do Zephyr (prefixo zsock_/NET_) em vez dos
 * nomes BSD sem prefixo: nesta versao do SDK os nomes sem prefixo (AF_INET,
 * struct sockaddr_in, socket(), connect()...) so existem via o modo de
 * compatibilidade de namespace (CONFIG_NET_NAMESPACE_COMPAT_MODE, ligado por
 * padrao) ou exigem CONFIG_POSIX_API. Os nomes com prefixo sao os que o
 * proprio Zephyr usa internamente (por exemplo subsys/net/lib/mqtt) e nao
 * dependem de nenhum dos dois.
 *
 * O descritor e protegido por um mutex: telemetria, botao e recepcao correm
 * em threads separadas e todas chamam transporte_enviar()/receber(), e uma
 * reconexao (transporte_fechar() + transporte_abrir()) pode acontecer no
 * meio disso. Sem essa exclusao, dois envios concorrentes intercalam bytes
 * no mesmo socket (a corrupcao que motivou este ajuste) e uma reconexao no
 * meio de um envio de outra thread pode fechar o descritor por baixo dela.
 * O mutex cobre a chamada inteira de cada funcao, incluindo a espera de
 * transporte_receber() -- custa uma pequena serializacao entre enviar e
 * receber (no pior caso, o tempo de `espera` de uma chamada), mas elimina
 * a classe inteira de corrida por um preco baixo para este lab.
 */
#if defined(CONFIG_LAB_TRANSPORTE_TCP)

#include <errno.h>

#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/net/socket.h>

#include "transporte.h"

LOG_MODULE_REGISTER(lab_transporte, CONFIG_LOG_DEFAULT_LEVEL);

static int sock = -1;
static K_MUTEX_DEFINE(transporte_mutex);

/* So chamar com o mutex ja adquirido. */
static void fechar_interno(void)
{
	if (sock >= 0) {
		zsock_close(sock);
		sock = -1;
	}
}

int transporte_abrir(void)
{
	struct net_sockaddr_in endereco = {0};
	int novo_sock;
	int ret;

	novo_sock = zsock_socket(NET_AF_INET, NET_SOCK_STREAM, 0);
	if (novo_sock < 0) {
		LOG_ERR("Falha ao criar o socket (%d)", -errno);
		return -errno;
	}

	endereco.sin_family = NET_AF_INET;
	endereco.sin_port = net_htons(CONFIG_LAB_PORTA);

	ret = net_addr_pton(NET_AF_INET, CONFIG_LAB_SERVIDOR_IP, &endereco.sin_addr);
	if (ret < 0) {
		LOG_ERR("CONFIG_LAB_SERVIDOR_IP invalido: %s", CONFIG_LAB_SERVIDOR_IP);
		zsock_close(novo_sock);
		return ret;
	}

	/* Conecta fora do mutex: e a parte que pode demorar (handshake TCP ou
	 * timeout de rede) e ainda nao mexe no descritor em uso pelas outras
	 * funcoes -- so o swap abaixo precisa da exclusao.
	 */
	ret = zsock_connect(novo_sock, (struct net_sockaddr *)&endereco, sizeof(endereco));
	if (ret < 0) {
		ret = -errno;
		LOG_ERR("Falha ao conectar em %s:%d (%d)",
			CONFIG_LAB_SERVIDOR_IP, CONFIG_LAB_PORTA, ret);
		zsock_close(novo_sock);
		return ret;
	}

	k_mutex_lock(&transporte_mutex, K_FOREVER);
	/* Fecha o descritor antigo antes de assumir o novo -- nunca os dois
	 * vivos ao mesmo tempo, nem o antigo pendurado.
	 */
	fechar_interno();
	sock = novo_sock;
	k_mutex_unlock(&transporte_mutex);

	LOG_INF("Conectado em %s:%d", CONFIG_LAB_SERVIDOR_IP, CONFIG_LAB_PORTA);
	return 0;
}

int transporte_enviar(const char *buf, size_t len)
{
	ssize_t ret;

	k_mutex_lock(&transporte_mutex, K_FOREVER);

	if (sock < 0) {
		k_mutex_unlock(&transporte_mutex);
		return -ENOTCONN;
	}

	ret = zsock_send(sock, buf, len, 0);
	if (ret < 0) {
		ret = -errno;
	}

	k_mutex_unlock(&transporte_mutex);
	return (int)ret;
}

int transporte_receber(char *buf, size_t len, k_timeout_t espera)
{
	struct zsock_pollfd pfd;
	int timeout_ms;
	int ret;

	k_mutex_lock(&transporte_mutex, K_FOREVER);

	if (sock < 0) {
		k_mutex_unlock(&transporte_mutex);
		return -ENOTCONN;
	}

	pfd.fd = sock;
	pfd.events = ZSOCK_POLLIN;
	pfd.revents = 0;

	timeout_ms = K_TIMEOUT_EQ(espera, K_FOREVER) ? -1 : (int)k_ticks_to_ms_floor64(espera.ticks);

	ret = zsock_poll(&pfd, 1, timeout_ms);
	if (ret < 0) {
		ret = -errno;
		k_mutex_unlock(&transporte_mutex);
		return ret;
	}
	if (ret == 0) {
		/* Nada chegou dentro de `espera`: nao e erro, a conexao segue
		 * presumida viva.
		 */
		k_mutex_unlock(&transporte_mutex);
		return 0;
	}

	ret = zsock_recv(sock, buf, len, 0);
	if (ret < 0) {
		ret = -errno;
		k_mutex_unlock(&transporte_mutex);
		return ret;
	}
	if (ret == 0) {
		/* recv() devolvendo 0 e o outro lado fechando a conexao de
		 * forma ordenada -- diferente de "nada chegou ainda". Devolve
		 * um codigo distinto para quem chama saber que precisa
		 * reabrir o transporte.
		 */
		k_mutex_unlock(&transporte_mutex);
		return -ECONNRESET;
	}

	k_mutex_unlock(&transporte_mutex);
	return ret;
}

void transporte_fechar(void)
{
	k_mutex_lock(&transporte_mutex, K_FOREVER);
	fechar_interno();
	k_mutex_unlock(&transporte_mutex);
}

#endif /* CONFIG_LAB_TRANSPORTE_TCP */
