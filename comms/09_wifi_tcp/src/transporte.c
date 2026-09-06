/* Codigo do curso (nrf-manaus-2).
 *
 * As tres implementacoes da interface transporte.h (TCP, HTTP, MQTT) moram
 * neste mesmo arquivo, cada uma sob o seu proprio
 * "#if defined(CONFIG_LAB_TRANSPORTE_...)" -- so uma delas entra no binario
 * (a escolha e a choice LAB_TRANSPORTE do Kconfig), e o main.c nao sabe qual.
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

#if defined(CONFIG_LAB_TRANSPORTE_HTTP)

/* HTTP nao tem conexao persistente: cada requisicao (POST ou GET) abre um
 * socket, faz o pedido com http_client_req(), le a resposta e fecha -- e o
 * padrao dos proprios exemplos do Zephyr para essa API (zephyr/samples/net/
 * sockets/http_client/src/main.c). O mutex aqui nao protege um descritor
 * compartilhado entre chamadas -- nao existe um, cada chamada tem o seu --
 * protege a mesma coisa que no TCP: que enviar() e receber() de threads
 * diferentes nunca executem a sequencia conectar/pedir/fechar ao mesmo
 * tempo, o que deixa o numero de sockets abertos (CONFIG_NET_MAX_CONTEXTS)
 * previsivel.
 *
 * transporte_receber() faz GET /comando -- e so isso: e o servidor que
 * teria que empurrar o comando, e HTTP nao tem como fazer isso sem o kit
 * perguntar primeiro. E o incomodo do HTTP que o README do lab 10 comenta:
 * ninguem avisa o kit, o kit tem que ficar perguntando.
 */

#include <errno.h>
#include <string.h>

#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/net/socket.h>
#include <zephyr/net/http/client.h>

#include "transporte.h"

LOG_MODULE_REGISTER(lab_transporte, CONFIG_LOG_DEFAULT_LEVEL);

static K_MUTEX_DEFINE(transporte_mutex);

/* Buffer de trabalho do http_client_req(): cabecalho + corpo brutos, como
 * chegam da rede. Nao e o buffer que o chamador passou -- esse (buf/len de
 * transporte_enviar/receber) recebe so o corpo, ja separado, via
 * resposta_cb() abaixo.
 */
#define HTTP_RECV_BUF_LEN 256
static uint8_t http_recv_buf[HTTP_RECV_BUF_LEN];

/* Timeout da troca HTTP em si (depois do connect()), nao o intervalo entre
 * tentativas de poll do GET /comando -- esse e o `espera` de
 * transporte_receber(), tratado mais abaixo.
 */
#define HTTP_TIMEOUT_MS 5000

/* Quando transporte_receber() e chamado com K_FOREVER (nao acontece hoje em
 * main.c, que sempre usa K_SECONDS(1), mas a interface permite): intervalo
 * de poll assumido, para nunca martelar o servidor sem parar.
 */
#define HTTP_POLL_ESPERA_PADRAO_MS 1000

struct http_ctx {
	uint16_t status_code;
	char *corpo;       /* NULL se a chamada nao quer o corpo (POST) */
	size_t corpo_max;
	size_t corpo_len;
};

static int resposta_cb(struct http_response *rsp, enum http_final_call final_data,
			void *user_data)
{
	struct http_ctx *ctx = user_data;
	size_t n = rsp->body_frag_len;

	ARG_UNUSED(final_data);

	ctx->status_code = rsp->http_status_code;

	if (ctx->corpo != NULL && rsp->body_frag_start != NULL && n > 0) {
		if (ctx->corpo_len + n > ctx->corpo_max) {
			n = ctx->corpo_max - ctx->corpo_len;
		}
		memcpy(ctx->corpo + ctx->corpo_len, rsp->body_frag_start, n);
		ctx->corpo_len += n;
	}

	return 0;
}

/* Abre um socket TCP novo e conecta no servidor -- uma conexao por
 * requisicao, o oposto do socket unico e duradouro do TCP puro.
 */
static int abrir_conexao(void)
{
	struct net_sockaddr_in endereco = {0};
	int sock;
	int ret;

	sock = zsock_socket(NET_AF_INET, NET_SOCK_STREAM, 0);
	if (sock < 0) {
		return -errno;
	}

	endereco.sin_family = NET_AF_INET;
	endereco.sin_port = net_htons(CONFIG_LAB_PORTA);

	ret = net_addr_pton(NET_AF_INET, CONFIG_LAB_SERVIDOR_IP, &endereco.sin_addr);
	if (ret < 0) {
		LOG_ERR("CONFIG_LAB_SERVIDOR_IP invalido: %s", CONFIG_LAB_SERVIDOR_IP);
		zsock_close(sock);
		return ret;
	}

	ret = zsock_connect(sock, (struct net_sockaddr *)&endereco, sizeof(endereco));
	if (ret < 0) {
		ret = -errno;
		zsock_close(sock);
		return ret;
	}

	return sock;
}

int transporte_abrir(void)
{
	struct net_sockaddr_in endereco = {0};

	/* Nao ha conexao para abrir de verdade (cada requisicao abre a sua) --
	 * so confere aqui que CONFIG_LAB_SERVIDOR_IP e um IPv4 valido, o
	 * mesmo erro que o TCP so detectaria no primeiro connect().
	 */
	if (net_addr_pton(NET_AF_INET, CONFIG_LAB_SERVIDOR_IP, &endereco.sin_addr) < 0) {
		LOG_ERR("CONFIG_LAB_SERVIDOR_IP invalido: %s", CONFIG_LAB_SERVIDOR_IP);
		return -EINVAL;
	}

	LOG_INF("HTTP pronto para %s:%d (uma conexao por requisicao)",
		CONFIG_LAB_SERVIDOR_IP, CONFIG_LAB_PORTA);
	return 0;
}

int transporte_enviar(const char *buf, size_t len)
{
	struct http_request req = {0};
	struct http_ctx ctx = {0};
	int sock;
	int ret;

	k_mutex_lock(&transporte_mutex, K_FOREVER);

	sock = abrir_conexao();
	if (sock < 0) {
		k_mutex_unlock(&transporte_mutex);
		return sock;
	}

	req.method = HTTP_POST;
	req.url = "/telemetria";
	req.host = CONFIG_LAB_SERVIDOR_IP;
	req.protocol = "HTTP/1.1";
	req.content_type_value = "application/json";
	req.payload = buf;
	req.payload_len = len;
	req.response = resposta_cb;
	req.recv_buf = http_recv_buf;
	req.recv_buf_len = sizeof(http_recv_buf);

	ret = http_client_req(sock, &req, HTTP_TIMEOUT_MS, &ctx);
	zsock_close(sock);

	k_mutex_unlock(&transporte_mutex);

	if (ret < 0) {
		return ret;
	}
	if (ctx.status_code != 200) {
		LOG_WRN("Servidor respondeu %u ao POST /telemetria", ctx.status_code);
		return -ECONNRESET;
	}
	return (int)len;
}

int transporte_receber(char *buf, size_t len, k_timeout_t espera)
{
	struct http_request req = {0};
	struct http_ctx ctx = {
		.corpo = buf,
		.corpo_max = len,
	};
	int64_t espera_ms;
	int sock;
	int ret;

	espera_ms = K_TIMEOUT_EQ(espera, K_FOREVER) ? HTTP_POLL_ESPERA_PADRAO_MS
						     : k_ticks_to_ms_floor64(espera.ticks);

	k_mutex_lock(&transporte_mutex, K_FOREVER);

	sock = abrir_conexao();
	if (sock < 0) {
		k_mutex_unlock(&transporte_mutex);
		return sock;
	}

	req.method = HTTP_GET;
	req.url = "/comando";
	req.host = CONFIG_LAB_SERVIDOR_IP;
	req.protocol = "HTTP/1.1";
	req.response = resposta_cb;
	req.recv_buf = http_recv_buf;
	req.recv_buf_len = sizeof(http_recv_buf);

	ret = http_client_req(sock, &req, HTTP_TIMEOUT_MS, &ctx);
	zsock_close(sock);

	k_mutex_unlock(&transporte_mutex);

	if (ret < 0) {
		return ret;
	}

	if (ctx.status_code == 204 || ctx.corpo_len == 0) {
		/* Nada pendente: dorme o resto do intervalo pedido antes de
		 * devolver "nada chegou", para o GET nao ser disparado de
		 * novo imediatamente -- sem isso, o polling martela o
		 * servidor a cada iteracao da thread de recepcao.
		 */
		k_sleep(K_MSEC(espera_ms));
		return 0;
	}
	if (ctx.status_code != 200) {
		LOG_WRN("Servidor respondeu %u ao GET /comando", ctx.status_code);
		return -ECONNRESET;
	}

	return (int)ctx.corpo_len;
}

void transporte_fechar(void)
{
	/* Nao ha descritor persistente para fechar: cada chamada de enviar/
	 * receber ja fecha o proprio socket assim que termina.
	 */
}

#endif /* CONFIG_LAB_TRANSPORTE_HTTP */

#if defined(CONFIG_LAB_TRANSPORTE_MQTT)

/* Cliente MQTT do Zephyr (zephyr/include/zephyr/net/mqtt.h). Ao contrario do
 * TCP e do HTTP, aqui o socket some por baixo da API: e o mqtt_client que
 * cria e guarda o descritor (client.transport.tcp.sock), e as chamadas
 * (mqtt_publish, mqtt_subscribe, mqtt_input, mqtt_live) so falam com esse
 * descritor internamente. O mutex protege a mesma coisa que nos outros dois
 * transportes -- a struct mqtt_client (`cliente`, abaixo) e os buffers
 * associados a ela, compartilhados entre as tres threads que chamam
 * enviar()/receber().
 *
 * Publica em CONFIG_LAB_MQTT_TOPICO com QoS 0 (no maximo uma vez, sem PUBACK)
 * -- combina com o payload deste lab, que ja e best-effort (perder uma
 * amostra de telemetria periodica nao e um problema; a proxima chega no
 * intervalo seguinte) e mantem o pacote no fio o mais enxuto possivel para
 * a comparacao de bytes do README. Assina "<topico>/comando" para o
 * downlink, tambem QoS 0.
 *
 * A pratica so acontece dentro de transporte_receber(): e a unica chamada
 * que faz poll no socket do cliente MQTT e chama mqtt_input() (processa o
 * que chegou -- inclusive um PUBLISH no topico de comando) e mqtt_live()
 * (manda PINGREQ se o keepalive estiver vencendo). transporte_enviar() so
 * chama mqtt_publish(), sem essa bombeada -- e o mesmo padrao do sample
 * zephyr/samples/net/mqtt_publisher (publish() e process_mqtt_and_sleep()
 * sao chamadas separadas). Como a thread de recepcao chama
 * transporte_receber() a cada 1 s (thread_recepcao() em src/main.c), o
 * cliente MQTT e bombeado nesse ritmo mesmo quando nao ha comando algum
 * pendente.
 */

#include <errno.h>
#include <stdio.h>
#include <string.h>

#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/net/socket.h>
#include <zephyr/net/mqtt.h>

#include "transporte.h"

LOG_MODULE_REGISTER(lab_transporte, CONFIG_LOG_DEFAULT_LEVEL);

static K_MUTEX_DEFINE(transporte_mutex);

#define MQTT_BUF_LEN 256
static uint8_t mqtt_rx_buf[MQTT_BUF_LEN];
static uint8_t mqtt_tx_buf[MQTT_BUF_LEN];

/* Tempo esperando o CONNACK depois do mqtt_connect() -- so manda o pacote
 * CONNECT; a confirmacao chega de forma assincrona, via mqtt_input(), igual
 * ao try_to_connect() do sample mqtt_publisher.
 */
#define MQTT_CONNACK_TIMEOUT_MS 5000

/* Identifica o cliente para o broker. Fixo de proposito -- cada bancada
 * deste curso roda o proprio mosquitto local (tools/README.md do lab 10),
 * entao nao ha dois clientes com o mesmo id no mesmo broker. Um curso com
 * broker compartilhado entre kits precisaria de um id por dispositivo.
 */
#define MQTT_CLIENT_ID "nrf-manaus-2-lab10"

static struct mqtt_client cliente;
static struct net_sockaddr_in endereco_broker;
static char topico_comando[sizeof(CONFIG_LAB_MQTT_TOPICO) + sizeof("/comando")];

static bool conectado;
static char comando_buf[64];
static size_t comando_len;
static bool comando_pendente;

static void evt_handler(struct mqtt_client *client, const struct mqtt_evt *evt)
{
	switch (evt->type) {
	case MQTT_EVT_CONNACK:
		conectado = (evt->result == 0);
		if (!conectado) {
			LOG_ERR("Broker recusou o CONNECT MQTT (%d)", evt->result);
		}
		break;

	case MQTT_EVT_DISCONNECT:
		LOG_WRN("MQTT desconectado (%d)", evt->result);
		conectado = false;
		break;

	case MQTT_EVT_PUBLISH: {
		size_t n = evt->param.publish.message.payload.len;
		int ret;

		if (n >= sizeof(comando_buf)) {
			LOG_WRN("Comando MQTT truncado (%zu > %zu bytes)", n,
				sizeof(comando_buf) - 1);
			n = sizeof(comando_buf) - 1;
		}

		ret = mqtt_readall_publish_payload(client, (uint8_t *)comando_buf, n);
		if (ret == 0) {
			comando_buf[n] = '\0';
			comando_len = n;
			comando_pendente = true;
		} else {
			LOG_WRN("Falha ao ler o payload do comando MQTT (%d)", ret);
		}
		break;
	}

	default:
		break;
	}
}

/* So chamar com o mutex ja adquirido. */
static void fechar_interno(void)
{
	mqtt_abort(&cliente);
	conectado = false;
	comando_pendente = false;
}

int transporte_abrir(void)
{
	struct mqtt_topic topico;
	struct mqtt_subscription_list lista;
	int64_t inicio;
	int ret;

	endereco_broker.sin_family = NET_AF_INET;
	endereco_broker.sin_port = net_htons(CONFIG_LAB_PORTA);
	ret = net_addr_pton(NET_AF_INET, CONFIG_LAB_SERVIDOR_IP, &endereco_broker.sin_addr);
	if (ret < 0) {
		LOG_ERR("CONFIG_LAB_SERVIDOR_IP invalido: %s", CONFIG_LAB_SERVIDOR_IP);
		return ret;
	}

	snprintf(topico_comando, sizeof(topico_comando), "%s/comando", CONFIG_LAB_MQTT_TOPICO);

	k_mutex_lock(&transporte_mutex, K_FOREVER);

	fechar_interno();

	mqtt_client_init(&cliente);
	cliente.broker = &endereco_broker;
	cliente.evt_cb = evt_handler;
	cliente.client_id.utf8 = (uint8_t *)MQTT_CLIENT_ID;
	cliente.client_id.size = sizeof(MQTT_CLIENT_ID) - 1;
	cliente.rx_buf = mqtt_rx_buf;
	cliente.rx_buf_size = sizeof(mqtt_rx_buf);
	cliente.tx_buf = mqtt_tx_buf;
	cliente.tx_buf_size = sizeof(mqtt_tx_buf);
	cliente.transport.type = MQTT_TRANSPORT_NON_SECURE;

	ret = mqtt_connect(&cliente);
	if (ret < 0) {
		LOG_ERR("Falha ao mandar o CONNECT MQTT (%d)", ret);
		k_mutex_unlock(&transporte_mutex);
		return ret;
	}

	inicio = k_uptime_get();
	while (!conectado && (k_uptime_get() - inicio) < MQTT_CONNACK_TIMEOUT_MS) {
		struct zsock_pollfd pfd = {
			.fd = cliente.transport.tcp.sock,
			.events = ZSOCK_POLLIN,
		};
		int32_t restante = (int32_t)(MQTT_CONNACK_TIMEOUT_MS -
					      (k_uptime_get() - inicio));

		if (zsock_poll(&pfd, 1, restante) > 0) {
			mqtt_input(&cliente);
		}
	}

	if (!conectado) {
		LOG_ERR("Tempo esgotado esperando o CONNACK do broker MQTT");
		fechar_interno();
		k_mutex_unlock(&transporte_mutex);
		return -ETIMEDOUT;
	}

	/* Nao espera o SUBACK: e a mesma simplificacao best-effort do QoS 0
	 * usado em todo o resto deste transporte. Um SUBACK perdido so atrasa
	 * o primeiro comando (chega no proximo PUBLISH do topico, depois que
	 * o broker confirmar a assinatura) -- nunca afeta a telemetria, que
	 * e o sentido inverso.
	 */
	topico.topic.utf8 = (uint8_t *)topico_comando;
	topico.topic.size = strlen(topico_comando);
	topico.qos = MQTT_QOS_0_AT_MOST_ONCE;

	lista.list = &topico;
	lista.list_count = 1;
	lista.message_id = 1;

	ret = mqtt_subscribe(&cliente, &lista);
	if (ret < 0) {
		LOG_WRN("Falha ao assinar %s (%d)", topico_comando, ret);
	}

	k_mutex_unlock(&transporte_mutex);

	LOG_INF("MQTT conectado em %s:%d, publicando em %s", CONFIG_LAB_SERVIDOR_IP,
		CONFIG_LAB_PORTA, CONFIG_LAB_MQTT_TOPICO);
	return 0;
}

int transporte_enviar(const char *buf, size_t len)
{
	struct mqtt_publish_param param = {0};
	int ret;

	k_mutex_lock(&transporte_mutex, K_FOREVER);

	if (!conectado) {
		k_mutex_unlock(&transporte_mutex);
		return -ENOTCONN;
	}

	param.message.topic.topic.utf8 = (uint8_t *)CONFIG_LAB_MQTT_TOPICO;
	param.message.topic.topic.size = strlen(CONFIG_LAB_MQTT_TOPICO);
	param.message.topic.qos = MQTT_QOS_0_AT_MOST_ONCE;
	param.message.payload.data = (uint8_t *)buf;
	param.message.payload.len = len;

	ret = mqtt_publish(&cliente, &param);

	k_mutex_unlock(&transporte_mutex);

	if (ret < 0) {
		return ret;
	}
	return (int)len;
}

int transporte_receber(char *buf, size_t len, k_timeout_t espera)
{
	struct zsock_pollfd pfd;
	int timeout_ms;
	int ret;
	size_t n;

	k_mutex_lock(&transporte_mutex, K_FOREVER);

	if (!conectado) {
		k_mutex_unlock(&transporte_mutex);
		return -ENOTCONN;
	}

	pfd.fd = cliente.transport.tcp.sock;
	pfd.events = ZSOCK_POLLIN;
	pfd.revents = 0;

	timeout_ms = K_TIMEOUT_EQ(espera, K_FOREVER) ? -1 : (int)k_ticks_to_ms_floor64(espera.ticks);

	ret = zsock_poll(&pfd, 1, timeout_ms);
	if (ret < 0) {
		ret = -errno;
		k_mutex_unlock(&transporte_mutex);
		return ret;
	}
	if (ret > 0) {
		ret = mqtt_input(&cliente);
		if (ret < 0) {
			LOG_WRN("Falha ao processar dado MQTT recebido (%d)", ret);
			conectado = false;
			k_mutex_unlock(&transporte_mutex);
			return -ECONNRESET;
		}
	}

	/* Mantem a sessao viva (PINGREQ se o keepalive estiver vencendo),
	 * independente de ter chegado algo no poll acima -- se nao chamar
	 * isso periodicamente, o broker derruba a conexao por keepalive
	 * mesmo com a rede saudavel.
	 */
	ret = mqtt_live(&cliente);
	if (ret < 0 && ret != -EAGAIN) {
		LOG_WRN("Falha no keepalive MQTT (%d)", ret);
		conectado = false;
		k_mutex_unlock(&transporte_mutex);
		return ret;
	}

	if (!conectado) {
		/* mqtt_input()/mqtt_live() podem ter processado um
		 * MQTT_EVT_DISCONNECT no meio da chamada -- o broker fechou a
		 * sessao.
		 */
		k_mutex_unlock(&transporte_mutex);
		return -ECONNRESET;
	}

	if (!comando_pendente) {
		k_mutex_unlock(&transporte_mutex);
		return 0;
	}

	n = MIN(comando_len, len);
	memcpy(buf, comando_buf, n);
	comando_pendente = false;

	k_mutex_unlock(&transporte_mutex);
	return (int)n;
}

void transporte_fechar(void)
{
	k_mutex_lock(&transporte_mutex, K_FOREVER);
	fechar_interno();
	k_mutex_unlock(&transporte_mutex);
}

#endif /* CONFIG_LAB_TRANSPORTE_MQTT */
