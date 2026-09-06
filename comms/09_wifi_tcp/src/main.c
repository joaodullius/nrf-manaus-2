/* Codigo do curso (nrf-manaus-2) -- nao vem do SDK.
 *
 * Lab 9: conecta na rede da sala, le temperatura e RSSI a cada
 * CONFIG_LAB_INTERVALO_MS e manda uma amostra pelo transporte configurado
 * (transporte.h). O botao sw0 manda uma amostra extra, imediata, com
 * "botao":true. Uma linha "LED 1"/"LED 0" vinda do servidor acende ou apaga
 * o led1.
 */
#include <errno.h>
#include <stdint.h>
#include <string.h>

#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/logging/log.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/drivers/sensor.h>
#include <zephyr/net/net_if.h>
#include <zephyr/net/net_mgmt.h>
#include <zephyr/net/net_event.h>
#include <zephyr/net/wifi_mgmt.h>

#include "payload.h"
#include "transporte.h"

LOG_MODULE_REGISTER(lab_wifi_tcp, CONFIG_LOG_DEFAULT_LEVEL);

/* Sensor de temperatura do die. O no vem habilitado pelo dtsi da placa
 * ("temp_sensor: &temp { status = "okay"; };"); o driver correto para o
 * nRF54L, confirmado no build (ver o relatorio da task), e o CONFIG_TEMP_NRF5
 * -- a compatible do no e "nordic,nrf-temp", que e a que esse driver cobre.
 */
#define TEMP_NODE DT_NODELABEL(temp_sensor)
static const struct device *const temp_dev = DEVICE_DT_GET(TEMP_NODE);

/* sw3 nao existe com o shield nrf7002eb2 nesta versao do SDK (o overlay
 * apaga o botao e o alias): o botao do lab e o sw0.
 */
#define SW0_NODE DT_ALIAS(sw0)
#define LED1_NODE DT_ALIAS(led1)

static const struct gpio_dt_spec botao = GPIO_DT_SPEC_GET(SW0_NODE, gpios);
static const struct gpio_dt_spec led1 = GPIO_DT_SPEC_GET(LED1_NODE, gpios);
static struct gpio_callback botao_cb_data;

static struct net_mgmt_event_callback wifi_cb;
static struct net_mgmt_event_callback net_cb;

static K_SEM_DEFINE(ip_pronto, 0, 1);
static K_SEM_DEFINE(botao_apertado, 0, 1);

static atomic_t proximo_seq;

/* Sentinela para "sensor de temperatura indisponivel": um valor fora da
 * faixa de qualquer leitura real (die temperature nunca chega a -300 C),
 * para o servidor conseguir distinguir uma falha de leitura de uma medida.
 */
#define TEMP_CC_INDISPONIVEL INT16_MIN

static int16_t ler_temp_cc(void)
{
	struct sensor_value val;
	int ret;

	if (!device_is_ready(temp_dev)) {
		return TEMP_CC_INDISPONIVEL;
	}

	ret = sensor_sample_fetch(temp_dev);
	if (ret < 0) {
		LOG_WRN("Falha ao ler o sensor de temperatura (%d)", ret);
		return TEMP_CC_INDISPONIVEL;
	}

	ret = sensor_channel_get(temp_dev, SENSOR_CHAN_DIE_TEMP, &val);
	if (ret < 0) {
		LOG_WRN("Falha ao converter a leitura de temperatura (%d)", ret);
		return TEMP_CC_INDISPONIVEL;
	}

	/* val1 = graus inteiros, val2 = milionesimos de grau (sensor_value). */
	return (int16_t)(val.val1 * 100 + val.val2 / 10000);
}

/* Sentinela para "RSSI indisponivel": INT8_MIN (-128 dBm) e fisicamente
 * implausivel para um link Wi-Fi associado (o piso de ruido normal fica bem
 * acima disso), entao serve para o servidor distinguir uma falha de consulta
 * de uma leitura real -- mesmo raciocinio do TEMP_CC_INDISPONIVEL acima.
 */
#define RSSI_DBM_INDISPONIVEL INT8_MIN

static int8_t ler_rssi_dbm(void)
{
	struct net_if *iface = net_if_get_first_wifi();
	struct wifi_iface_status status = {0};
	int rssi;

	if (!iface) {
		return RSSI_DBM_INDISPONIVEL;
	}

	if (net_mgmt(NET_REQUEST_WIFI_IFACE_STATUS, iface, &status, sizeof(status))) {
		LOG_WRN("Falha ao consultar o status do Wi-Fi");
		return RSSI_DBM_INDISPONIVEL;
	}

	/* status.rssi ja vem como int8_t, mas o valor passa por um "int" antes
	 * do cast final para nao truncar em silencio se essa faixa mudar numa
	 * versao futura do driver.
	 */
	rssi = status.rssi;
	if (rssi < INT8_MIN || rssi > INT8_MAX) {
		return RSSI_DBM_INDISPONIVEL;
	}
	return (int8_t)rssi;
}

/* Espera entre tentativas de (re)conexao: cresce a cada falha ate o teto,
 * para nao martelar a rede quando o servidor esta fora do ar, mas nunca
 * desiste -- e o exercicio do lab desligar o servidor de proposito e ver o
 * firmware retomar quando ele volta.
 */
#define RECONEXAO_ESPERA_INICIAL_MS 1000u
#define RECONEXAO_ESPERA_MAXIMA_MS  30000u

/* Numero de tentativas seguidas, sem nunca ter conectado uma vez, ate avisar
 * que o problema provavelmente e configuracao (IP/porta errados, ou PC e kit
 * em redes diferentes) e nao um servidor que caiu.
 */
#define RECONEXAO_TENTATIVAS_AVISO_CONFIG 5

/* Uma vez que a primeira conexao aconteceu, uma queda depois e so queda --
 * o aviso de "confira a configuracao" abaixo so faz sentido antes disso.
 */
static bool ja_conectou_alguma_vez;

static void abrir_com_backoff(void)
{
	uint32_t espera_ms = RECONEXAO_ESPERA_INICIAL_MS;
	uint32_t tentativas = 0;
	int ret;

	while (1) {
		ret = transporte_abrir();
		if (ret == 0) {
			ja_conectou_alguma_vez = true;
			return;
		}

		tentativas++;
		if (!ja_conectou_alguma_vez && tentativas == RECONEXAO_TENTATIVAS_AVISO_CONFIG) {
			LOG_ERR("Sem conseguir conectar depois de %u tentativas -- confira "
				"CONFIG_LAB_SERVIDOR_IP e CONFIG_LAB_PORTA, e se o PC e o "
				"kit estao na mesma rede", tentativas);
		}

		LOG_WRN("Falha ao abrir o transporte (%d); nova tentativa em %u ms",
			ret, espera_ms);
		k_sleep(K_MSEC(espera_ms));
		espera_ms = MIN(espera_ms * 2, RECONEXAO_ESPERA_MAXIMA_MS);
	}
}

/* So uma reconexao de fato acontece por vez: se a telemetria e a recepcao
 * detectarem a queda quase juntas, a segunda so adquire o mutex depois que a
 * primeira termina. Pode fazer um fechar+abrir redundante logo em seguida
 * (o transporte ja esta bom outra vez) -- desperdicio pequeno e inofensivo,
 * nao uma corrida: o mutex de transporte.c garante que o descritor nunca
 * fica inconsistente.
 */
static K_MUTEX_DEFINE(reconexao_mutex);

static void reconectar_transporte(void)
{
	k_mutex_lock(&reconexao_mutex, K_FOREVER);
	transporte_fechar();
	abrir_com_backoff();
	k_mutex_unlock(&reconexao_mutex);
}

static void montar_e_enviar(bool botao_pressionado)
{
	struct payload_amostra amostra = {
		.seq = (uint32_t)atomic_inc(&proximo_seq),
		.uptime_ms = (uint32_t)k_uptime_get(),
		.temp_cc = ler_temp_cc(),
		.rssi_dbm = ler_rssi_dbm(),
		.botao = botao_pressionado,
	};
	char linha[128];
	int n;
	int ret;

	n = payload_montar(linha, sizeof(linha), &amostra);
	if (n < 0) {
		LOG_ERR("Falha ao montar o payload (%d)", n);
		return;
	}

	ret = transporte_enviar(linha, (size_t)n);
	if (ret < 0) {
		LOG_ERR("Falha ao enviar a amostra %u (%d); reconectando", amostra.seq, ret);
		reconectar_transporte();
	}
}

static void thread_telemetria(void)
{
	while (1) {
		montar_e_enviar(false);
		k_msleep(CONFIG_LAB_INTERVALO_MS);
	}
}

static void thread_botao(void)
{
	while (1) {
		k_sem_take(&botao_apertado, K_FOREVER);
		montar_e_enviar(true);
	}
}

static void thread_recepcao(void)
{
	char linha[64];

	while (1) {
		int n = transporte_receber(linha, sizeof(linha) - 1, K_SECONDS(1));

		if (n == 0) {
			/* Tempo esgotado: nada chegou, conexao presumida viva. */
			continue;
		}
		if (n < 0) {
			if (n == -ECONNRESET) {
				LOG_WRN("Servidor fechou a conexao; reconectando");
			} else {
				LOG_WRN("Falha ao receber (%d); reconectando", n);
			}
			reconectar_transporte();
			continue;
		}

		linha[n] = '\0';

		if (strncmp(linha, "LED 1", 5) == 0) {
			gpio_pin_set_dt(&led1, 1);
		} else if (strncmp(linha, "LED 0", 5) == 0) {
			gpio_pin_set_dt(&led1, 0);
		}
	}
}

K_THREAD_DEFINE(telemetria_id, 2048, thread_telemetria, NULL, NULL, NULL, 7, 0, -1);
K_THREAD_DEFINE(botao_id, 1024, thread_botao, NULL, NULL, NULL, 7, 0, -1);
K_THREAD_DEFINE(recepcao_id, 2048, thread_recepcao, NULL, NULL, NULL, 7, 0, -1);

static void botao_pressionado_cb(const struct device *dev, struct gpio_callback *cb,
				  uint32_t pins)
{
	ARG_UNUSED(dev);
	ARG_UNUSED(cb);
	ARG_UNUSED(pins);

	k_sem_give(&botao_apertado);
}

static void configurar_botao(void)
{
	int ret;

	if (!gpio_is_ready_dt(&botao)) {
		LOG_ERR("Botao sw0 nao esta pronto");
		return;
	}

	ret = gpio_pin_configure_dt(&botao, GPIO_INPUT);
	if (ret < 0) {
		LOG_ERR("Falha ao configurar o botao sw0 (%d)", ret);
		return;
	}

	ret = gpio_pin_interrupt_configure_dt(&botao, GPIO_INT_EDGE_TO_ACTIVE);
	if (ret < 0) {
		LOG_ERR("Falha ao configurar a interrupcao do botao sw0 (%d)", ret);
		return;
	}

	gpio_init_callback(&botao_cb_data, botao_pressionado_cb, BIT(botao.pin));
	gpio_add_callback(botao.port, &botao_cb_data);
}

static void configurar_led(void)
{
	if (!gpio_is_ready_dt(&led1)) {
		LOG_ERR("LED led1 nao esta pronto");
		return;
	}

	gpio_pin_configure_dt(&led1, GPIO_OUTPUT_INACTIVE);
}

static void handler_wifi(struct net_mgmt_event_callback *cb, uint64_t evento,
			  struct net_if *iface)
{
	ARG_UNUSED(iface);

	if (evento != NET_EVENT_WIFI_CONNECT_RESULT) {
		return;
	}

	const struct wifi_status *status = (const struct wifi_status *)cb->info;

	if (status->status) {
		LOG_ERR("Falha ao conectar ao Wi-Fi (%d)", status->status);
	} else {
		LOG_INF("Conectado ao Wi-Fi");
	}
}

static void handler_net(struct net_mgmt_event_callback *cb, uint64_t evento,
			 struct net_if *iface)
{
	ARG_UNUSED(iface);

	if (evento != NET_EVENT_IPV4_DHCP_BOUND) {
		return;
	}

	const struct net_if_dhcpv4 *dhcpv4 = cb->info;
	char ip[NET_IPV4_ADDR_LEN];

	net_addr_ntop(NET_AF_INET, &dhcpv4->requested_ip, ip, sizeof(ip));
	LOG_INF("IP obtido por DHCP: %s", ip);

	k_sem_give(&ip_pronto);
}

static int conectar_wifi(void)
{
	struct net_if *iface = net_if_get_first_wifi();

	if (!iface) {
		LOG_ERR("Nenhuma interface Wi-Fi encontrada");
		return -ENODEV;
	}

	if (net_mgmt(NET_REQUEST_WIFI_CONNECT_STORED, iface, NULL, 0)) {
		LOG_ERR("Pedido de conexao Wi-Fi falhou");
		return -EIO;
	}

	LOG_INF("Conexao Wi-Fi solicitada");
	return 0;
}

int main(void)
{
	net_mgmt_init_event_callback(&wifi_cb, handler_wifi, NET_EVENT_WIFI_CONNECT_RESULT);
	net_mgmt_add_event_callback(&wifi_cb);

	net_mgmt_init_event_callback(&net_cb, handler_net, NET_EVENT_IPV4_DHCP_BOUND);
	net_mgmt_add_event_callback(&net_cb);

	configurar_botao();
	configurar_led();

	if (conectar_wifi() < 0) {
		return -EIO;
	}

	LOG_INF("Aguardando IP por DHCP...");
	k_sem_take(&ip_pronto, K_FOREVER);

	/* Nunca desiste: espera crescente ate um teto, nao uma tentativa so. */
	abrir_com_backoff();

	k_thread_start(telemetria_id);
	k_thread_start(botao_id);
	k_thread_start(recepcao_id);

	return 0;
}
